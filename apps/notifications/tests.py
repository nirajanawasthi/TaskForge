from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.organizations.models import Membership
from apps.organizations.services import create_organization
from apps.projects.models import Project, ProjectMember
from apps.tasks.models import Task

from .models import Notification

PASSWORD = "Tf-Demo-2026-x9"
S = Task.Status
K = Notification.Kind


def make_user(email):
    return User.objects.create_user(email=email, password=PASSWORD)


def make_project(org, name, is_private, creator, members):
    project = Project.objects.create(
        organization=org, name=name, is_private=is_private, created_by=creator
    )
    for user in members:
        ProjectMember.objects.create(project=project, user=user)
    return project


class NotificationTestBase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = make_user("admin@example.com")
        self.org = create_organization(user=self.admin, name="Acme")
        self.lead = make_user("lead@example.com")
        self.member = make_user("member@example.com")
        self.member2 = make_user("member2@example.com")
        Membership.objects.create(
            user=self.lead, organization=self.org, role=Membership.Role.TEAM_LEAD
        )
        Membership.objects.create(
            user=self.member, organization=self.org, role=Membership.Role.MEMBER
        )
        Membership.objects.create(
            user=self.member2, organization=self.org, role=Membership.Role.MEMBER
        )
        self.project = make_project(
            self.org, "Alpha", False, self.admin, [self.admin, self.lead, self.member]
        )

    def make_task(self, assignee=None, status=S.TODO, created_by=None, project=None):
        return Task.objects.create(
            project=project or self.project,
            title="Write docs",
            status=status,
            assignee=assignee,
            created_by=created_by or self.admin,
        )

    def notes(self, user, **filters):
        return Notification.objects.filter(recipient=user, **filters)

    def post_task(self, user, payload, project=None):
        project = project or self.project
        self.client.force_authenticate(user)
        url = reverse("tasks:task-list", args=[self.org.pk, project.pk])
        return self.client.post(url, payload, format="json")

    def patch_task(self, user, task, payload):
        self.client.force_authenticate(user)
        url = reverse(
            "tasks:task-detail", args=[self.org.pk, task.project_id, task.pk]
        )
        return self.client.patch(url, payload, format="json")

    def act(self, user, task, action):
        self.client.force_authenticate(user)
        url = reverse(
            "workflows:task-transition", args=[self.org.pk, task.project_id, task.pk]
        )
        return self.client.post(url, {"action": action}, format="json")

    def comment(self, user, task, body="Looks good"):
        self.client.force_authenticate(user)
        url = reverse(
            "comments:comment-list", args=[self.org.pk, task.project_id, task.pk]
        )
        return self.client.post(url, {"body": body}, format="json")


class NotificationTriggerTests(NotificationTestBase):
    def test_assigning_on_create_notifies_the_assignee(self):
        response = self.post_task(
            self.lead, {"title": "Write docs", "assignee_email": self.member.email}
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        notes = self.notes(self.member)
        self.assertEqual(notes.count(), 1)
        self.assertEqual(notes[0].kind, K.TASK_ASSIGNED)
        self.assertIn("Write docs", notes[0].message)
        self.assertIn(self.lead.email, notes[0].message)
        self.assertEqual(self.notes(self.lead).count(), 0)

    def test_self_assignment_does_not_notify(self):
        self.post_task(
            self.lead, {"title": "Mine", "assignee_email": self.lead.email}
        )
        self.assertEqual(Notification.objects.count(), 0)

    def test_reassigning_notifies_only_the_new_assignee(self):
        task = self.make_task(assignee=self.member)
        self.patch_task(self.lead, task, {"assignee_email": self.admin.email})
        self.assertEqual(self.notes(self.admin, kind=K.TASK_ASSIGNED).count(), 1)
        self.assertEqual(self.notes(self.member).count(), 0)

    def test_unassigning_notifies_nobody(self):
        task = self.make_task(assignee=self.member)
        self.patch_task(self.lead, task, {"assignee_email": None})
        self.assertEqual(Notification.objects.count(), 0)

    def test_submit_for_review_notifies_the_task_creator(self):
        task = self.make_task(assignee=self.member, created_by=self.admin)
        self.act(self.member, task, "start")
        self.act(self.member, task, "submit_for_review")
        notes = self.notes(self.admin)
        self.assertEqual([n.kind for n in notes], [K.REVIEW_REQUESTED])
        self.assertEqual(self.notes(self.member).count(), 0)

    def test_review_outcomes_notify_the_assignee(self):
        approved = self.make_task(assignee=self.member, status=S.IN_REVIEW)
        changes = self.make_task(assignee=self.member, status=S.IN_REVIEW)
        self.act(self.lead, approved, "approve")
        self.act(self.lead, changes, "request_changes")
        kinds = sorted(n.kind for n in self.notes(self.member))
        self.assertEqual(kinds, sorted([K.TASK_APPROVED, K.CHANGES_REQUESTED]))

    def test_reopening_notifies_the_assignee(self):
        task = self.make_task(assignee=self.member, status=S.DONE)
        self.act(self.lead, task, "reopen")
        self.assertEqual([n.kind for n in self.notes(self.member)], [K.TASK_REOPENED])

    def test_comment_notifies_assignee_and_creator_but_not_the_author(self):
        task = self.make_task(assignee=self.member, created_by=self.admin)
        self.comment(self.lead, task)
        self.assertEqual(self.notes(self.admin, kind=K.COMMENT_ADDED).count(), 1)
        self.assertEqual(self.notes(self.member, kind=K.COMMENT_ADDED).count(), 1)
        self.assertEqual(self.notes(self.lead).count(), 0)
        self.comment(self.member, task)
        self.assertEqual(self.notes(self.admin, kind=K.COMMENT_ADDED).count(), 2)
        self.assertEqual(self.notes(self.member, kind=K.COMMENT_ADDED).count(), 1)
        self.assertEqual(self.notes(self.lead).count(), 0)

    def test_user_who_can_no_longer_see_the_project_is_not_notified(self):
        secret = make_project(
            self.org, "Secret", True, self.admin, [self.admin, self.lead]
        )
        task = self.make_task(assignee=self.lead, created_by=self.member, project=secret)
        self.comment(self.admin, task)
        self.assertEqual(self.notes(self.lead).count(), 1)
        self.assertEqual(self.notes(self.member).count(), 0)

    def test_failed_request_creates_no_notification(self):
        response = self.post_task(
            self.lead, {"title": "T", "assignee_email": self.member2.email}
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Notification.objects.count(), 0)


class NotificationApiTests(NotificationTestBase):
    def setUp(self):
        super().setUp()
        self.task = self.make_task(assignee=self.member)
        self.list_url = reverse("notifications:notification-list")

    def make_note(self, user, kind=K.TASK_ASSIGNED, is_read=False):
        return Notification.objects.create(
            recipient=user, task=self.task, kind=kind, message="Hello", is_read=is_read
        )

    def read_url(self, note):
        return reverse("notifications:notification-read", args=[note.pk])

    def test_requires_authentication(self):
        self.assertEqual(
            self.client.get(self.list_url).status_code, status.HTTP_401_UNAUTHORIZED
        )
        self.assertEqual(
            self.client.post(
                reverse("notifications:notification-read-all")
            ).status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_list_shows_only_own_notifications_newest_first(self):
        first = self.make_note(self.member)
        second = self.make_note(self.member, kind=K.COMMENT_ADDED)
        self.make_note(self.admin)
        self.client.force_authenticate(self.member)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            [item["id"] for item in response.data["results"]], [second.pk, first.pk]
        )

    def test_notification_carries_ids_needed_to_open_the_task(self):
        self.make_note(self.member)
        self.client.force_authenticate(self.member)
        item = self.client.get(self.list_url).data["results"][0]
        self.assertEqual(item["task_id"], self.task.pk)
        self.assertEqual(item["project_id"], self.project.pk)
        self.assertEqual(item["organization_id"], self.org.pk)
        self.assertFalse(item["is_read"])

    def test_filter_by_read_state_and_kind(self):
        old = self.make_note(self.member, is_read=True)
        new = self.make_note(self.member, kind=K.COMMENT_ADDED)
        self.client.force_authenticate(self.member)
        unread = self.client.get(self.list_url, {"is_read": "false"})
        comments = self.client.get(self.list_url, {"kind": "comment_added"})
        self.assertEqual([i["id"] for i in unread.data["results"]], [new.pk])
        self.assertEqual([i["id"] for i in comments.data["results"]], [new.pk])
        self.assertNotIn(old.pk, [i["id"] for i in unread.data["results"]])

    def test_unread_count(self):
        self.make_note(self.member)
        self.make_note(self.member)
        self.make_note(self.member, is_read=True)
        self.make_note(self.admin)
        self.client.force_authenticate(self.member)
        url = reverse("notifications:notification-unread-count")
        self.assertEqual(self.client.get(url).data, {"unread": 2})

    def test_mark_one_read_is_idempotent(self):
        note = self.make_note(self.member)
        self.client.force_authenticate(self.member)
        first = self.client.post(self.read_url(note))
        self.assertEqual(first.status_code, status.HTTP_200_OK)
        self.assertTrue(first.data["is_read"])
        note.refresh_from_db()
        stamped = note.read_at
        self.assertIsNotNone(stamped)
        second = self.client.post(self.read_url(note))
        self.assertEqual(second.status_code, status.HTTP_200_OK)
        note.refresh_from_db()
        self.assertEqual(note.read_at, stamped)

    def test_cannot_mark_someone_elses_notification(self):
        note = self.make_note(self.admin)
        self.client.force_authenticate(self.member)
        response = self.client.post(self.read_url(note))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        note.refresh_from_db()
        self.assertFalse(note.is_read)

    def test_read_all_marks_only_own_notifications(self):
        self.make_note(self.admin)
        self.make_note(self.admin)
        theirs = self.make_note(self.member)
        self.client.force_authenticate(self.admin)
        url = reverse("notifications:notification-read-all")
        self.assertEqual(self.client.post(url).data, {"marked": 2})
        self.assertEqual(self.client.post(url).data, {"marked": 0})
        theirs.refresh_from_db()
        self.assertFalse(theirs.is_read)

    def test_list_is_paginated(self):
        self.make_note(self.member)
        self.client.force_authenticate(self.member)
        response = self.client.get(self.list_url)
        self.assertEqual(
            set(response.data), {"count", "next", "previous", "results"}
        )

    def test_notifications_cannot_be_created_or_deleted_through_the_api(self):
        note = self.make_note(self.member)
        self.client.force_authenticate(self.member)
        created = self.client.post(self.list_url, {"message": "x"}, format="json")
        deleted = self.client.delete(self.read_url(note))
        self.assertEqual(created.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        self.assertEqual(deleted.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        self.assertTrue(Notification.objects.filter(pk=note.pk).exists())


class NotificationEdgeCaseTests(NotificationTestBase):
    def test_task_without_assignee_notifies_nobody_and_does_not_crash(self):
        task = self.make_task(assignee=None, status=S.IN_REVIEW)
        response = self.act(self.lead, task, "approve")
        self.assertLess(response.status_code, 500)
        self.assertEqual(Notification.objects.count(), 0)

    def test_user_removed_from_the_organization_is_not_notified(self):
        task = self.make_task(assignee=self.member, created_by=self.admin)
        Membership.objects.filter(user=self.member, organization=self.org).delete()
        self.comment(self.lead, task)
        self.assertEqual(self.notes(self.member).count(), 0)
        self.assertEqual(self.notes(self.admin).count(), 1)
