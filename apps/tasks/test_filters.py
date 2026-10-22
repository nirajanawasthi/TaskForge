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
S = Task.Status
P = Task.Priority


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


class TaskFilterTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = make_user("admin@example.com")
        self.org = create_organization(user=self.admin, name="Acme")
        self.lead = make_user("lead@example.com")
        self.member = make_user("member@example.com")
        add_to_org(self.org, self.lead, Membership.Role.TEAM_LEAD)
        add_to_org(self.org, self.member, Membership.Role.MEMBER)
        self.project = make_project(
            self.org, "Alpha", False, self.admin, [self.admin, self.lead, self.member]
        )
        self.url = reverse("tasks:task-list", args=[self.org.pk, self.project.pk])
        self.today = timezone.localdate()
        day = timedelta
        self.t1 = self.make_task("Write docs", S.TODO, P.LOW, self.member, self.today + day(days=5))
        self.t2 = self.make_task("Fix login bug", S.IN_PROGRESS, P.URGENT, self.lead, self.today - day(days=2))
        self.t3 = self.make_task("Design logo", S.IN_REVIEW, P.MEDIUM, None, None)
        self.t4 = self.make_task("Deploy app", S.DONE, P.HIGH, self.member, self.today - day(days=10))
        self.t5 = self.make_task(
            "Update docs", S.TODO, P.HIGH, self.member, self.today - day(days=1),
            description="Mentions the login flow",
        )
        self.client.force_authenticate(self.admin)

    def make_task(self, title, task_status, priority, assignee, due_date, description="", project=None):
        return Task.objects.create(
            project=project or self.project,
            title=title,
            description=description,
            status=task_status,
            priority=priority,
            assignee=assignee,
            due_date=due_date,
            created_by=self.admin,
        )

    def ids(self, **params):
        response = self.client.get(self.url, params)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        return [task["id"] for task in response.data["results"]]

    def pks(self, *tasks):
        return [task.pk for task in tasks]

    def test_list_is_paginated_with_defaults(self):
        response = self.client.get(self.url)
        self.assertEqual(
            set(response.data), {"count", "next", "previous", "results"}
        )
        self.assertEqual(response.data["count"], 5)
        self.assertEqual(len(response.data["results"]), 5)

    def test_page_size_parameter_and_maximum(self):
        Task.objects.bulk_create(
            [
                Task(project=self.project, title=f"Bulk {i}", created_by=self.admin)
                for i in range(100)
            ]
        )
        big = self.client.get(self.url, {"page_size": 1000})
        self.assertEqual(big.data["count"], 105)
        self.assertEqual(len(big.data["results"]), 100)
        small = self.client.get(self.url, {"page_size": 2, "page": 2})
        self.assertEqual(len(small.data["results"]), 2)
        self.assertIsNotNone(small.data["next"])
        self.assertIsNotNone(small.data["previous"])

    def test_filter_by_multiple_statuses(self):
        found = self.ids(status=["todo", "in_progress"])
        self.assertEqual(set(found), set(self.pks(self.t1, self.t2, self.t5)))

    def test_filter_by_priority(self):
        found = self.ids(priority="high")
        self.assertEqual(set(found), set(self.pks(self.t4, self.t5)))

    def test_invalid_filter_choice_is_rejected(self):
        response = self.client.get(self.url, {"status": "bogus"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_filter_by_assignee_email_is_case_insensitive(self):
        found = self.ids(assignee_email="MEMBER@Example.com")
        self.assertEqual(set(found), set(self.pks(self.t1, self.t4, self.t5)))

    def test_assigned_to_me_and_unassigned(self):
        self.client.force_authenticate(self.member)
        mine = self.ids(assigned_to_me="true")
        others = self.ids(assigned_to_me="false")
        unassigned = self.ids(unassigned="true")
        self.assertEqual(set(mine), set(self.pks(self.t1, self.t4, self.t5)))
        self.assertEqual(set(others), set(self.pks(self.t2, self.t3)))
        self.assertEqual(unassigned, self.pks(self.t3))

    def test_overdue_excludes_done_and_undated_tasks(self):
        overdue = self.ids(overdue="true")
        not_overdue = self.ids(overdue="false")
        self.assertEqual(set(overdue), set(self.pks(self.t2, self.t5)))
        self.assertEqual(set(not_overdue), set(self.pks(self.t1, self.t3, self.t4)))

    def test_due_date_range(self):
        found = self.ids(
            due_after=(self.today - timedelta(days=3)).isoformat(),
            due_before=(self.today + timedelta(days=10)).isoformat(),
        )
        self.assertEqual(set(found), set(self.pks(self.t1, self.t2, self.t5)))

    def test_search_matches_title_and_description(self):
        login = self.ids(search="login")
        docs = self.ids(search="docs")
        self.assertEqual(set(login), set(self.pks(self.t2, self.t5)))
        self.assertEqual(set(docs), set(self.pks(self.t1, self.t5)))

    def test_ordering_by_due_date(self):
        ascending = self.ids(ordering="due_date")
        descending = self.ids(ordering="-due_date")
        expected = self.pks(self.t4, self.t2, self.t5, self.t1, self.t3)
        self.assertEqual(ascending, expected)
        self.assertEqual(descending, list(reversed(expected)))

    def test_ordering_by_priority_uses_rank_and_breaks_ties_by_id(self):
        descending = self.ids(ordering="-priority")
        ascending = self.ids(ordering="priority")
        self.assertEqual(
            descending, self.pks(self.t2, self.t5, self.t4, self.t3, self.t1)
        )
        self.assertEqual(
            ascending, self.pks(self.t1, self.t3, self.t5, self.t4, self.t2)
        )

    def test_invalid_ordering_field_is_rejected(self):
        response = self.client.get(self.url, {"ordering": "password"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_filters_stay_inside_the_project(self):
        other = make_project(self.org, "Beta", False, self.admin, [self.admin])
        self.make_task("Elsewhere", S.TODO, P.LOW, None, None, project=other)
        found = self.ids(status="todo")
        self.assertEqual(set(found), set(self.pks(self.t1, self.t5)))
