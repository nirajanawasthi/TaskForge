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
from apps.tasks.models import Task

from .models import ActivityLog

PASSWORD = "Tf-Demo-2026-x9"
A = ActivityLog.Action


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


class ActivityApiTests(TestCase):
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

    def tasks_url(self):
        return reverse("tasks:task-list", args=[self.org.pk, self.project.pk])

    def task_url(self, task):
        return reverse(
            "tasks:task-detail", args=[self.org.pk, task.project_id, task.pk]
        )

    def activity_url(self, task):
        return reverse(
            "activity_logs:activity-list",
            args=[self.org.pk, task.project_id, task.pk],
        )

    def transition_url(self, task):
        return reverse(
            "workflows:task-transition", args=[self.org.pk, task.project_id, task.pk]
        )

    def make_task(self, assignee=None, project=None):
        return Task.objects.create(
            project=project or self.project,
            title="Write docs",
            created_by=self.admin,
            assignee=assignee,
        )

    def logs(self, task):
        return list(ActivityLog.objects.filter(task=task).order_by("id"))

    def test_requires_authentication(self):
        task = self.make_task()
        response = self.client.get(self.activity_url(task))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_non_organization_member_gets_404(self):
        task = self.make_task()
        self.client.force_authenticate(self.outsider)
        response = self.client.get(self.activity_url(task))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_creating_task_logs_activity(self):
        self.client.force_authenticate(self.lead)
        response = self.client.post(
            self.tasks_url(),
            {"title": "T", "assignee_email": "member@example.com"},
            format="json",
        )
        task = Task.objects.get(pk=response.data["id"])
        logs = self.logs(task)
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0].action, A.TASK_CREATED)
        self.assertEqual(logs[0].actor, self.lead)
        self.assertEqual(
            logs[0].details, {"title": "T", "assignee": "member@example.com"}
        )

    def test_updating_fields_logs_only_real_changes(self):
        self.client.force_authenticate(self.lead)
        created = self.client.post(self.tasks_url(), {"title": "T"}, format="json")
        task = Task.objects.get(pk=created.data["id"])
        tomorrow = (timezone.localdate() + timedelta(days=1)).isoformat()
        self.client.patch(
            self.task_url(task),
            {"title": "New", "priority": "high", "description": "", "due_date": tomorrow},
            format="json",
        )
        updated = [log for log in self.logs(task) if log.action == A.TASK_UPDATED]
        self.assertEqual(len(updated), 1)
        self.assertEqual(
            updated[0].details["changes"],
            {
                "title": {"from": "T", "to": "New"},
                "priority": {"from": "medium", "to": "high"},
                "due_date": {"from": None, "to": tomorrow},
            },
        )

    def test_patch_with_no_changes_logs_nothing(self):
        task = self.make_task(assignee=self.member)
        self.client.force_authenticate(self.lead)
        response = self.client.patch(
            self.task_url(task),
            {"title": "Write docs", "assignee_email": "member@example.com"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self.logs(task), [])

    def test_reassigning_logs_assignee_change(self):
        task = self.make_task(assignee=self.member)
        self.client.force_authenticate(self.lead)
        self.client.patch(
            self.task_url(task), {"assignee_email": self.lead.email}, format="json"
        )
        self.client.patch(self.task_url(task), {"assignee_email": None}, format="json")
        logs = self.logs(task)
        self.assertEqual([log.action for log in logs], [A.ASSIGNEE_CHANGED] * 2)
        self.assertEqual(
            logs[0].details, {"from": "member@example.com", "to": "lead@example.com"}
        )
        self.assertEqual(logs[1].details, {"from": "lead@example.com", "to": None})

    def test_workflow_transition_logs_status_change(self):
        task = self.make_task(assignee=self.member)
        self.client.force_authenticate(self.member)
        response = self.client.post(
            self.transition_url(task), {"action": "start"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        logs = self.logs(task)
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0].action, A.STATUS_CHANGED)
        self.assertEqual(logs[0].actor, self.member)
        self.assertEqual(
            logs[0].details, {"action": "start", "from": "todo", "to": "in_progress"}
        )

    def test_history_is_newest_first_and_names_the_actor(self):
        self.client.force_authenticate(self.lead)
        created = self.client.post(self.tasks_url(), {"title": "T"}, format="json")
        task = Task.objects.get(pk=created.data["id"])
        self.client.force_authenticate(self.admin)
        self.client.patch(self.task_url(task), {"title": "New"}, format="json")
        response = self.client.get(self.activity_url(task))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            [(item["action"], item["actor"]) for item in response.data],
            [("task_updated", "admin@example.com"), ("task_created", "lead@example.com")],
        )

    def test_regular_member_can_read_history(self):
        task = self.make_task(assignee=self.member)
        self.client.force_authenticate(self.lead)
        self.client.patch(self.task_url(task), {"title": "New"}, format="json")
        self.client.force_authenticate(self.member)
        response = self.client.get(self.activity_url(task))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_hidden_private_project_returns_404(self):
        secret = make_project(self.org, "Secret", True, self.admin, [self.admin, self.lead])
        task = self.make_task(project=secret)
        self.client.force_authenticate(self.member2)
        response = self.client.get(self.activity_url(task))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_history_is_read_only(self):
        task = self.make_task()
        ActivityLog.objects.create(task=task, actor=self.admin, action=A.TASK_CREATED)
        self.client.force_authenticate(self.admin)
        url = self.activity_url(task)
        for method in ("post", "put", "patch", "delete"):
            response = getattr(self.client, method)(url, {}, format="json")
            self.assertEqual(
                response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED, method
            )
        self.assertEqual(ActivityLog.objects.filter(task=task).count(), 1)

    def test_failed_request_logs_nothing(self):
        self.client.force_authenticate(self.lead)
        response = self.client.post(
            self.tasks_url(),
            {"title": "T", "assignee_email": self.outsider.email},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Task.objects.count(), 0)
        self.assertEqual(ActivityLog.objects.count(), 0)
