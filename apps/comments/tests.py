from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.activity_logs.models import ActivityLog
from apps.organizations.models import Membership
from apps.organizations.services import create_organization
from apps.projects.models import Project, ProjectMember
from apps.tasks.models import Task

from .models import Comment

PASSWORD = "Tf-Demo-2026-x9"


def make_user(email):
    return User.objects.create_user(email=email, password=PASSWORD)


def add_to_org(org, user, role):
    return Membership.objects.create(user=user, organization=org, role=role)


def make_project(org, name, is_private, creator, members):
    project = Project.objects.create(
        organization=org, name=name, is_private=is_private, created_by=creator
    )
    for user in members:
        ProjectMember.objects.create(project=project, user=user)
    return project


class CommentApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = make_user("admin@example.com")
        self.org = create_organization(user=self.admin, name="Acme")
        self.lead = make_user("lead@example.com")
        self.member = make_user("member@example.com")
        self.member2 = make_user("member2@example.com")
        self.outsider = make_user("outsider@example.com")
        add_to_org(self.org, self.lead, Membership.Role.TEAM_LEAD)
        add_to_org(self.org, self.member, Membership.Role.MEMBER)
        add_to_org(self.org, self.member2, Membership.Role.MEMBER)
        self.project = make_project(
            self.org, "Alpha", False, self.admin, [self.admin, self.lead, self.member]
        )
        self.task = Task.objects.create(
            project=self.project, title="Write docs", created_by=self.admin
        )

    def list_url(self, task=None):
        task = task or self.task
        return reverse(
            "comments:comment-list", args=[self.org.pk, task.project_id, task.pk]
        )

    def detail_url(self, comment, task=None):
        task = task or comment.task
        return reverse(
            "comments:comment-detail",
            args=[self.org.pk, task.project_id, task.pk, comment.pk],
        )

    def make_comment(self, author=None, task=None, body="Looks good"):
        return Comment.objects.create(
            task=task or self.task, author=author or self.member, body=body
        )

    def test_requires_authentication(self):
        response = self.client.get(self.list_url())
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_non_organization_member_gets_404(self):
        self.client.force_authenticate(self.outsider)
        listing = self.client.get(self.list_url())
        create = self.client.post(self.list_url(), {"body": "Hi"}, format="json")
        self.assertEqual(listing.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(create.status_code, status.HTTP_404_NOT_FOUND)

    def test_regular_member_can_comment_and_list(self):
        self.client.force_authenticate(self.member2)
        response = self.client.post(self.list_url(), {"body": "First!"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["author"], "member2@example.com")
        listing = self.client.get(self.list_url())
        self.assertEqual([c["body"] for c in listing.data["results"]], ["First!"])

    def test_comment_is_recorded_in_activity(self):
        self.client.force_authenticate(self.member)
        response = self.client.post(self.list_url(), {"body": "Hi"}, format="json")
        log = ActivityLog.objects.get(task=self.task)
        self.assertEqual(log.action, ActivityLog.Action.COMMENT_ADDED)
        self.assertEqual(log.actor, self.member)
        self.assertEqual(log.details, {"comment_id": response.data["id"]})

    def test_blank_body_is_rejected(self):
        self.client.force_authenticate(self.member)
        for body in ("", "   "):
            response = self.client.post(self.list_url(), {"body": body}, format="json")
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
            self.assertIn("body", response.data)
        self.assertEqual(Comment.objects.count(), 0)

    def test_too_long_body_is_rejected(self):
        self.client.force_authenticate(self.member)
        response = self.client.post(
            self.list_url(), {"body": "x" * 2001}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("body", response.data)

    def test_author_and_task_in_payload_are_ignored(self):
        other = Task.objects.create(
            project=self.project, title="Other", created_by=self.admin
        )
        self.client.force_authenticate(self.member)
        payload = {"body": "Hi", "author": self.admin.pk, "task": other.pk}
        response = self.client.post(self.list_url(), payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        comment = Comment.objects.get(pk=response.data["id"])
        self.assertEqual(comment.author, self.member)
        self.assertEqual(comment.task, self.task)

    def test_hidden_private_project_returns_404(self):
        secret = make_project(self.org, "Secret", True, self.admin, [self.admin, self.lead])
        task = Task.objects.create(project=secret, title="Hidden", created_by=self.admin)
        self.client.force_authenticate(self.member2)
        listing = self.client.get(self.list_url(task))
        create = self.client.post(self.list_url(task), {"body": "Hi"}, format="json")
        self.assertEqual(listing.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(create.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(Comment.objects.count(), 0)

    def test_author_can_edit_own_comment(self):
        comment = self.make_comment()
        self.client.force_authenticate(self.member)
        response = self.client.patch(
            self.detail_url(comment), {"body": "Edited"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        comment.refresh_from_db()
        self.assertEqual(comment.body, "Edited")

    def test_other_users_cannot_edit_or_delete(self):
        comment = self.make_comment()
        for user in (self.lead, self.admin):
            self.client.force_authenticate(user)
            patch = self.client.patch(
                self.detail_url(comment), {"body": "Hacked"}, format="json"
            )
            delete = self.client.delete(self.detail_url(comment))
            self.assertEqual(patch.status_code, status.HTTP_403_FORBIDDEN)
            self.assertEqual(delete.status_code, status.HTTP_403_FORBIDDEN)
        comment.refresh_from_db()
        self.assertEqual(comment.body, "Looks good")

    def test_author_can_delete_own_comment(self):
        comment = self.make_comment()
        self.client.force_authenticate(self.member)
        response = self.client.delete(self.detail_url(comment))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Comment.objects.filter(pk=comment.pk).exists())

    def test_comment_under_wrong_task_returns_404(self):
        other = Task.objects.create(
            project=self.project, title="Other", created_by=self.admin
        )
        comment = self.make_comment()
        self.client.force_authenticate(self.member)
        url = self.detail_url(comment, task=other)
        patch = self.client.patch(url, {"body": "X"}, format="json")
        delete = self.client.delete(url)
        self.assertEqual(patch.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(delete.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(Comment.objects.filter(pk=comment.pk).exists())

    def test_put_is_not_allowed(self):
        comment = self.make_comment()
        self.client.force_authenticate(self.member)
        response = self.client.put(
            self.detail_url(comment), {"body": "X"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
