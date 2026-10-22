from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.organizations.models import Membership
from apps.organizations.services import create_organization
from apps.projects.models import Project, ProjectMember

from .models import Task

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


class TaskApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = make_user("admin@example.com")
        self.org = create_organization(user=self.admin, name="Acme")
        self.manager = make_user("manager@example.com")
        self.lead = make_user("lead@example.com")
        self.member = make_user("member@example.com")
        self.member2 = make_user("member2@example.com")
        self.outsider = make_user("outsider@example.com")
        add_to_org(self.org, self.manager, Membership.Role.MANAGER)
        add_to_org(self.org, self.lead, Membership.Role.TEAM_LEAD)
        add_to_org(self.org, self.member, Membership.Role.MEMBER)
        add_to_org(self.org, self.member2, Membership.Role.MEMBER)
        self.project = make_project(
            self.org, "Alpha", False, self.admin, [self.admin, self.lead, self.member]
        )
        self.list_url = self.list_url_for(self.project)

    def list_url_for(self, project, org=None):
        org = org or self.org
        return reverse("tasks:task-list", args=[org.pk, project.pk])

    def detail_url(self, task, project=None, org=None):
        org = org or self.org
        project = project or task.project
        return reverse("tasks:task-detail", args=[org.pk, project.pk, task.pk])

    def make_task(self, project=None, title="Write docs", assignee=None):
        return Task.objects.create(
            project=project or self.project,
            title=title,
            created_by=self.admin,
            assignee=assignee,
        )

    def test_requires_authentication(self):
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_non_organization_member_gets_404(self):
        self.client.force_authenticate(self.outsider)
        listing = self.client.get(self.list_url)
        create = self.client.post(self.list_url, {"title": "T"}, format="json")
        self.assertEqual(listing.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(create.status_code, status.HTTP_404_NOT_FOUND)

    def test_admin_creates_task_with_defaults(self):
        self.client.force_authenticate(self.admin)
        response = self.client.post(self.list_url, {"title": "Write docs"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["status"], "todo")
        self.assertEqual(response.data["priority"], "medium")
        self.assertIsNone(response.data["assignee"])
        self.assertEqual(response.data["created_by"], "admin@example.com")

    def test_manager_not_on_project_can_create(self):
        self.client.force_authenticate(self.manager)
        response = self.client.post(self.list_url, {"title": "T"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_team_lead_can_create(self):
        self.client.force_authenticate(self.lead)
        response = self.client.post(self.list_url, {"title": "T"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_regular_member_cannot_create(self):
        self.client.force_authenticate(self.member)
        response = self.client.post(self.list_url, {"title": "T"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(Task.objects.count(), 0)

    def test_regular_member_can_list_and_retrieve(self):
        task = self.make_task()
        self.client.force_authenticate(self.member)
        listing = self.client.get(self.list_url)
        detail = self.client.get(self.detail_url(task))
        self.assertEqual([t["id"] for t in listing.data["results"]], [task.pk])
        self.assertEqual(detail.status_code, status.HTTP_200_OK)

    def test_create_with_assignee_by_email(self):
        self.client.force_authenticate(self.lead)
        payload = {"title": "T", "assignee_email": "MEMBER@Example.com"}
        response = self.client.post(self.list_url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["assignee"], "member@example.com")

    def test_assignee_must_be_project_member(self):
        self.client.force_authenticate(self.lead)
        for email in (self.member2.email, self.outsider.email, "nobody@example.com"):
            response = self.client.post(
                self.list_url, {"title": "T", "assignee_email": email}, format="json"
            )
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
            self.assertIn("assignee_email", response.data)
        self.assertEqual(Task.objects.count(), 0)

    def test_status_project_and_creator_in_payload_are_ignored(self):
        other = make_project(self.org, "Beta", False, self.admin, [self.admin])
        self.client.force_authenticate(self.lead)
        payload = {
            "title": "T",
            "status": "done",
            "project": other.pk,
            "created_by": self.outsider.pk,
            "id": 9999,
        }
        response = self.client.post(self.list_url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        task = Task.objects.get(pk=response.data["id"])
        self.assertEqual(task.status, Task.Status.TODO)
        self.assertEqual(task.project, self.project)
        self.assertEqual(task.created_by, self.lead)
        self.assertNotEqual(task.pk, 9999)

    def test_title_is_required(self):
        self.client.force_authenticate(self.lead)
        response = self.client.post(self.list_url, {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("title", response.data)

    def test_past_due_date_is_rejected(self):
        self.client.force_authenticate(self.lead)
        yesterday = (timezone.localdate() - timedelta(days=1)).isoformat()
        response = self.client.post(
            self.list_url, {"title": "T", "due_date": yesterday}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("due_date", response.data)

    def test_today_and_future_due_dates_are_accepted(self):
        self.client.force_authenticate(self.lead)
        today = timezone.localdate()
        for day in (today, today + timedelta(days=7)):
            response = self.client.post(
                self.list_url, {"title": "T", "due_date": day.isoformat()}, format="json"
            )
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_invalid_priority_is_rejected(self):
        self.client.force_authenticate(self.lead)
        response = self.client.post(
            self.list_url, {"title": "T", "priority": "critical"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("priority", response.data)

    def test_lead_can_update_task_fields(self):
        task = self.make_task()
        self.client.force_authenticate(self.lead)
        tomorrow = (timezone.localdate() + timedelta(days=1)).isoformat()
        payload = {"title": "New", "priority": "urgent", "due_date": tomorrow}
        response = self.client.patch(self.detail_url(task), payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        task.refresh_from_db()
        self.assertEqual(task.title, "New")
        self.assertEqual(task.priority, "urgent")
        self.assertEqual(task.due_date.isoformat(), tomorrow)

    def test_reassign_and_unassign(self):
        task = self.make_task(assignee=self.member)
        self.client.force_authenticate(self.lead)
        reassigned = self.client.patch(
            self.detail_url(task), {"assignee_email": self.lead.email}, format="json"
        )
        self.assertEqual(reassigned.data["assignee"], "lead@example.com")
        unassigned = self.client.patch(
            self.detail_url(task), {"assignee_email": None}, format="json"
        )
        self.assertEqual(unassigned.status_code, status.HTTP_200_OK)
        task.refresh_from_db()
        self.assertIsNone(task.assignee)

    def test_patch_without_assignee_keeps_assignee(self):
        task = self.make_task(assignee=self.member)
        self.client.force_authenticate(self.lead)
        self.client.patch(self.detail_url(task), {"title": "Renamed"}, format="json")
        task.refresh_from_db()
        self.assertEqual(task.assignee, self.member)

    def test_regular_member_cannot_update(self):
        task = self.make_task()
        self.client.force_authenticate(self.member)
        response = self.client.patch(self.detail_url(task), {"title": "X"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        task.refresh_from_db()
        self.assertEqual(task.title, "Write docs")

    def test_hidden_private_project_returns_404_for_everything(self):
        secret = make_project(self.org, "Secret", True, self.admin, [self.admin, self.lead])
        task = self.make_task(project=secret, title="Hidden")
        for user in (self.member, self.manager):
            self.client.force_authenticate(user)
            responses = [
                self.client.get(self.list_url_for(secret)),
                self.client.post(self.list_url_for(secret), {"title": "T"}, format="json"),
                self.client.get(self.detail_url(task)),
                self.client.patch(self.detail_url(task), {"title": "X"}, format="json"),
            ]
            for response in responses:
                self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        task.refresh_from_db()
        self.assertEqual(task.title, "Hidden")

    def test_admin_sees_tasks_of_private_project_without_membership(self):
        secret = make_project(self.org, "Secret", True, self.lead, [self.lead])
        self.make_task(project=secret, title="Hidden")
        self.client.force_authenticate(self.admin)
        response = self.client.get(self.list_url_for(secret))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)

    def test_task_from_another_project_returns_404(self):
        other = make_project(self.org, "Beta", False, self.admin, [self.admin])
        task = self.make_task(project=other)
        self.client.force_authenticate(self.admin)
        url = reverse("tasks:task-detail", args=[self.org.pk, self.project.pk, task.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_project_from_another_organization_returns_404(self):
        other_admin = make_user("other-admin@example.com")
        other_org = create_organization(user=other_admin, name="Other Org")
        foreign = make_project(other_org, "Foreign", False, other_admin, [other_admin])
        self.client.force_authenticate(self.admin)
        url = reverse("tasks:task-list", args=[self.org.pk, foreign.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_put_and_delete_are_not_allowed(self):
        task = self.make_task()
        self.client.force_authenticate(self.admin)
        put = self.client.put(self.detail_url(task), {"title": "X"}, format="json")
        delete = self.client.delete(self.detail_url(task))
        self.assertEqual(put.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        self.assertEqual(delete.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        self.assertTrue(Task.objects.filter(pk=task.pk).exists())
