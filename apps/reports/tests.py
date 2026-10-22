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

PASSWORD = "Tf-Demo-2026-x9"
S = Task.Status
P = Task.Priority


def make_user(email):
    return User.objects.create_user(email=email, password=PASSWORD)


def make_project(org, name, is_private, creator, members):
    project = Project.objects.create(
        organization=org, name=name, is_private=is_private, created_by=creator
    )
    for user in members:
        ProjectMember.objects.create(project=project, user=user)
    return project


class ReportTestBase(TestCase):
    """Organization A has a public and a private project; organization B has noise."""

    def setUp(self):
        self.client = APIClient()
        self.today = timezone.localdate()
        self.admin = make_user("admin@example.com")
        self.org = create_organization(user=self.admin, name="Acme")
        self.lead = make_user("lead@example.com")
        self.member = make_user("member@example.com")
        self.outsider = make_user("outsider@example.com")
        Membership.objects.create(
            user=self.lead, organization=self.org, role=Membership.Role.TEAM_LEAD
        )
        Membership.objects.create(
            user=self.member, organization=self.org, role=Membership.Role.MEMBER
        )
        self.org_b = create_organization(user=self.outsider, name="Other Org")

        self.alpha = make_project(
            self.org, "Alpha", False, self.admin, [self.admin, self.lead, self.member]
        )
        self.secret = make_project(
            self.org, "Secret", True, self.admin, [self.admin, self.lead]
        )
        project_b = make_project(
            self.org_b, "Foreign", False, self.outsider, [self.outsider]
        )

        self.a1 = self.task(self.alpha, "A1", S.TODO, P.LOW, self.member, 3)
        self.a2 = self.task(self.alpha, "A2", S.IN_PROGRESS, P.HIGH, self.lead, -2)
        self.a3 = self.task(self.alpha, "A3", S.IN_REVIEW, P.MEDIUM, None, None)
        self.a4 = self.task(self.alpha, "A4", S.DONE, P.URGENT, self.member, -9)
        self.s1 = self.task(self.secret, "S1", S.TODO, P.URGENT, self.lead, -5)
        self.s2 = self.task(self.secret, "S2", S.IN_PROGRESS, P.LOW, None, 10)
        self.b1 = self.task(
            project_b, "B1", S.TODO, P.HIGH, self.outsider, -20, creator=self.outsider
        )

    def task(self, project, title, task_status, priority, assignee, days, creator=None):
        return Task.objects.create(
            project=project,
            title=title,
            status=task_status,
            priority=priority,
            assignee=assignee,
            due_date=None if days is None else self.today + timedelta(days=days),
            created_by=creator or self.admin,
        )

    def dashboard_url(self, org=None):
        return reverse("reports:dashboard", args=[(org or self.org).pk])

    def overdue_url(self, org=None):
        return reverse("reports:overdue", args=[(org or self.org).pk])

    def overdue_ids(self, user, **params):
        self.client.force_authenticate(user)
        response = self.client.get(self.overdue_url(), params)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        return [item["id"] for item in response.data["results"]]


class DashboardTests(ReportTestBase):
    ADMIN_TASKS = {
        "total": 6,
        "by_status": {"todo": 2, "in_progress": 2, "in_review": 1, "done": 1},
        "overdue": 2,
        "due_soon": 1,
        "unassigned": 2,
        "completion_rate": 16.7,
    }
    WORKLOAD = [
        {"email": "lead@example.com", "open": 2, "overdue": 2, "done": 0},
        {"email": "member@example.com", "open": 1, "overdue": 0, "done": 1},
    ]

    def test_requires_authentication(self):
        response = self.client.get(self.dashboard_url())
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_non_organization_member_gets_404(self):
        self.client.force_authenticate(self.outsider)
        response = self.client.get(self.dashboard_url())
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_admin_sees_totals_for_all_visible_projects(self):
        self.client.force_authenticate(self.admin)
        response = self.client.get(self.dashboard_url())
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["projects"], 2)
        self.assertEqual(response.data["tasks"], self.ADMIN_TASKS)
        self.assertEqual(
            response.data["open_by_priority"],
            {"low": 2, "medium": 1, "high": 1, "urgent": 1},
        )
        self.assertEqual(response.data["my_tasks"], {"open": 0, "overdue": 0})
        self.assertEqual(response.data["workload"], self.WORKLOAD)

    def test_other_organization_data_is_not_counted(self):
        self.assertEqual(Task.objects.count(), 7)
        self.client.force_authenticate(self.admin)
        response = self.client.get(self.dashboard_url())
        self.assertEqual(response.data["tasks"]["total"], 6)
        self.assertEqual(response.data["tasks"]["overdue"], 2)

    def test_regular_member_sees_only_visible_projects_and_no_workload(self):
        self.client.force_authenticate(self.member)
        response = self.client.get(self.dashboard_url())
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["projects"], 1)
        self.assertEqual(
            response.data["tasks"],
            {
                "total": 4,
                "by_status": {"todo": 1, "in_progress": 1, "in_review": 1, "done": 1},
                "overdue": 1,
                "due_soon": 1,
                "unassigned": 1,
                "completion_rate": 25.0,
            },
        )
        self.assertEqual(
            response.data["open_by_priority"],
            {"low": 1, "medium": 1, "high": 1, "urgent": 0},
        )
        self.assertEqual(response.data["my_tasks"], {"open": 1, "overdue": 0})
        self.assertNotIn("workload", response.data)

    def test_team_lead_gets_workload_and_personal_counts(self):
        self.client.force_authenticate(self.lead)
        response = self.client.get(self.dashboard_url())
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["tasks"], self.ADMIN_TASKS)
        self.assertEqual(response.data["my_tasks"], {"open": 2, "overdue": 2})
        self.assertEqual(response.data["workload"], self.WORKLOAD)

    def test_empty_organization_returns_zeros(self):
        solo = make_user("solo@example.com")
        empty_org = create_organization(user=solo, name="Empty")
        self.client.force_authenticate(solo)
        response = self.client.get(self.dashboard_url(empty_org))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["projects"], 0)
        self.assertEqual(response.data["tasks"]["total"], 0)
        self.assertEqual(response.data["tasks"]["completion_rate"], 0.0)
        self.assertEqual(response.data["workload"], [])

    def test_post_is_not_allowed(self):
        self.client.force_authenticate(self.admin)
        response = self.client.post(self.dashboard_url(), {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)


class OverdueReportTests(ReportTestBase):
    def test_requires_authentication(self):
        response = self.client.get(self.overdue_url())
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_non_organization_member_gets_404(self):
        self.client.force_authenticate(self.outsider)
        response = self.client.get(self.overdue_url())
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_admin_sees_overdue_tasks_oldest_first(self):
        self.client.force_authenticate(self.admin)
        response = self.client.get(self.overdue_url())
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data["results"]
        self.assertEqual([item["id"] for item in results], [self.s1.pk, self.a2.pk])
        self.assertEqual([item["days_overdue"] for item in results], [5, 2])
        self.assertEqual([item["project"] for item in results], ["Secret", "Alpha"])
        self.assertEqual(
            [item["assignee"] for item in results],
            ["lead@example.com", "lead@example.com"],
        )

    def test_regular_member_does_not_see_hidden_project_tasks(self):
        self.assertEqual(self.overdue_ids(self.member), [self.a2.pk])

    def test_filter_by_project_does_not_reveal_hidden_projects(self):
        self.assertEqual(
            self.overdue_ids(self.admin, project=self.alpha.pk), [self.a2.pk]
        )
        hidden = self.overdue_ids(self.member, project=self.secret.pk)
        missing = self.overdue_ids(self.member, project=999999)
        self.assertEqual(hidden, [])
        self.assertEqual(hidden, missing)

    def test_filter_by_assignee_email(self):
        found = self.overdue_ids(self.admin, assignee_email="LEAD@example.com")
        self.assertEqual(found, [self.s1.pk, self.a2.pk])
        self.assertEqual(
            self.overdue_ids(self.admin, assignee_email="member@example.com"), []
        )

    def test_response_is_paginated(self):
        self.client.force_authenticate(self.admin)
        response = self.client.get(self.overdue_url())
        self.assertEqual(
            set(response.data), {"count", "next", "previous", "results"}
        )
        self.assertEqual(response.data["count"], 2)

    def test_post_is_not_allowed(self):
        self.client.force_authenticate(self.admin)
        response = self.client.post(self.overdue_url(), {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
