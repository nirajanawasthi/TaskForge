from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.organizations.models import Membership
from apps.organizations.services import create_organization
from apps.projects.models import Project, ProjectMember
from apps.tasks.models import Task

PASSWORD = "Tf-Demo-2026-x9"
S = Task.Status


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


class TransitionApiTests(TestCase):
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
            self.org,
            "Alpha",
            False,
            self.admin,
            [self.admin, self.lead, self.member, self.member2],
        )

    def make_task(self, status=S.TODO, assignee=None, project=None):
        return Task.objects.create(
            project=project or self.project,
            title="Write docs",
            created_by=self.admin,
            assignee=assignee,
            status=status,
        )

    def url(self, task, project=None):
        project = project or task.project
        return reverse(
            "workflows:task-transition", args=[self.org.pk, project.pk, task.pk]
        )

    def act(self, user, task, action, project=None):
        self.client.force_authenticate(user)
        return self.client.post(
            self.url(task, project), {"action": action}, format="json"
        )

    def assert_status(self, task, expected):
        task.refresh_from_db()
        self.assertEqual(task.status, expected)

    def test_requires_authentication(self):
        task = self.make_task(assignee=self.member)
        self.client.force_authenticate(None)
        response = self.client.post(self.url(task), {"action": "start"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_non_organization_member_gets_404(self):
        task = self.make_task(assignee=self.member)
        response = self.act(self.outsider, task, "start")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assert_status(task, S.TODO)

    def test_hidden_private_project_returns_404_not_403(self):
        secret = make_project(self.org, "Secret", True, self.admin, [self.admin, self.lead])
        task = self.make_task(assignee=self.lead, project=secret)
        for user in (self.member2, self.manager):
            response = self.act(user, task, "start")
            self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assert_status(task, S.TODO)

    def test_assignee_can_start_and_submit_for_review(self):
        task = self.make_task(assignee=self.member)
        started = self.act(self.member, task, "start")
        self.assertEqual(started.status_code, status.HTTP_200_OK)
        self.assertEqual(started.data["status"], "in_progress")
        submitted = self.act(self.member, task, "submit_for_review")
        self.assertEqual(submitted.data["status"], "in_review")
        self.assert_status(task, S.IN_REVIEW)

    def test_regular_member_who_is_not_assignee_cannot_start(self):
        task = self.make_task(assignee=self.member)
        response = self.act(self.member2, task, "start")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assert_status(task, S.TODO)

    def test_team_lead_can_start_task_assigned_to_someone_else(self):
        task = self.make_task(assignee=self.member)
        response = self.act(self.lead, task, "start")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assert_status(task, S.IN_PROGRESS)

    def test_cannot_start_unassigned_task(self):
        task = self.make_task()
        response = self.act(self.lead, task, "start")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assert_status(task, S.TODO)

    def test_invalid_transition_is_rejected_and_state_is_unchanged(self):
        task = self.make_task(assignee=self.member)
        response = self.act(self.lead, task, "approve")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("action", response.data)
        self.assert_status(task, S.TODO)

    def test_assignee_cannot_approve_own_task(self):
        task = self.make_task(status=S.IN_REVIEW, assignee=self.member)
        response = self.act(self.member, task, "approve")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assert_status(task, S.IN_REVIEW)

    def test_admin_assignee_cannot_approve_own_task(self):
        task = self.make_task(status=S.IN_REVIEW, assignee=self.admin)
        response = self.act(self.admin, task, "approve")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assert_status(task, S.IN_REVIEW)

    def test_lead_approves_task_in_review(self):
        task = self.make_task(status=S.IN_REVIEW, assignee=self.member)
        response = self.act(self.lead, task, "approve")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "done")
        self.assert_status(task, S.DONE)

    def test_lead_requests_changes(self):
        task = self.make_task(status=S.IN_REVIEW, assignee=self.member)
        response = self.act(self.manager, task, "request_changes")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assert_status(task, S.IN_PROGRESS)

    def test_assignee_cannot_request_changes(self):
        task = self.make_task(status=S.IN_REVIEW, assignee=self.lead)
        response = self.act(self.lead, task, "request_changes")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assert_status(task, S.IN_REVIEW)

    def test_regular_member_cannot_approve(self):
        task = self.make_task(status=S.IN_REVIEW, assignee=self.member)
        response = self.act(self.member2, task, "approve")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assert_status(task, S.IN_REVIEW)

    def test_lead_can_reopen_done_task(self):
        task = self.make_task(status=S.DONE, assignee=self.member)
        response = self.act(self.lead, task, "reopen")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assert_status(task, S.IN_PROGRESS)

    def test_regular_member_cannot_reopen(self):
        task = self.make_task(status=S.DONE, assignee=self.member)
        response = self.act(self.member, task, "reopen")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assert_status(task, S.DONE)

    def test_unknown_action_is_rejected(self):
        task = self.make_task(assignee=self.member)
        response = self.act(self.lead, task, "explode")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("action", response.data)
        self.assert_status(task, S.TODO)

    def test_full_review_cycle(self):
        task = self.make_task(assignee=self.member)
        steps = [
            (self.member, "start", S.IN_PROGRESS),
            (self.member, "submit_for_review", S.IN_REVIEW),
            (self.lead, "request_changes", S.IN_PROGRESS),
            (self.member, "submit_for_review", S.IN_REVIEW),
            (self.lead, "approve", S.DONE),
            (self.lead, "reopen", S.IN_PROGRESS),
        ]
        for user, action, expected in steps:
            response = self.act(user, task, action)
            self.assertEqual(response.status_code, status.HTTP_200_OK, action)
            self.assert_status(task, expected)

    def test_status_cannot_be_changed_through_task_patch(self):
        task = self.make_task(assignee=self.member)
        self.client.force_authenticate(self.lead)
        url = reverse("tasks:task-detail", args=[self.org.pk, self.project.pk, task.pk])
        response = self.client.patch(url, {"status": "done"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assert_status(task, S.TODO)

    def test_task_from_another_project_returns_404(self):
        other = make_project(self.org, "Beta", False, self.admin, [self.admin])
        task = self.make_task(assignee=self.member, project=other)
        response = self.act(self.lead, task, "start", project=self.project)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assert_status(task, S.TODO)

    def test_get_is_not_allowed(self):
        task = self.make_task(assignee=self.member)
        self.client.force_authenticate(self.lead)
        response = self.client.get(self.url(task))
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
