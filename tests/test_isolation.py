from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.organizations.models import Membership, Organization
from apps.organizations.services import create_organization
from apps.projects.models import Project, ProjectMember
from apps.activity_logs.models import ActivityLog
from apps.comments.models import Comment
from apps.tasks.models import Task

PASSWORD = "Tf-Demo-2026-x9"
MISSING = 999999
METHODS = ("get", "post", "patch", "put", "delete")

# (url name, ids it needs in URL order)
ENDPOINTS = [
    ("organizations:organization-detail", ("org",)),
    ("organizations:membership-list", ("org",)),
    ("organizations:membership-detail", ("org", "membership")),
    ("projects:project-list", ("org",)),
    ("projects:project-detail", ("org", "project")),
    ("projects:project-member-list", ("org", "project")),
    ("projects:project-member-detail", ("org", "project", "pm")),
    ("tasks:task-list", ("org", "project")),
    ("tasks:task-detail", ("org", "project", "task")),
    ("workflows:task-transition", ("org", "project", "task")),
    ("comments:comment-list", ("org", "project", "task")),
    ("comments:comment-detail", ("org", "project", "task", "comment")),
    ("activity_logs:activity-list", ("org", "project", "task")),
    ("reports:dashboard", ("org",)),
    ("reports:overdue", ("org",)),
]

# A real user, so a leaky endpoint would visibly succeed in adding them.
BODY = {
    "name": "Changed",
    "title": "Changed",
    "description": "Changed",
    "email": "target@example.com",
    "assignee_email": "target@example.com",
    "role": "admin",
    "action": "start",
    "body": "Changed",
}


def make_user(email):
    return User.objects.create_user(email=email, password=PASSWORD)


def make_project(org, name, is_private, creator, members):
    project = Project.objects.create(
        organization=org, name=name, is_private=is_private, created_by=creator
    )
    for user in members:
        ProjectMember.objects.create(project=project, user=user)
    return project


def snapshot():
    return {
        model.__name__: list(model.objects.order_by("pk").values())
        for model in (
            Organization,
            Membership,
            Project,
            ProjectMember,
            Task,
            Comment,
            ActivityLog,
        )
    }


class IsolationSweepTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.alice = make_user("alice@example.com")
        self.bob = make_user("bob@example.com")
        self.carol = make_user("carol@example.com")
        self.target = make_user("target@example.com")

        self.org_a = create_organization(user=self.alice, name="Org A")
        self.org_b = create_organization(user=self.bob, name="Org B")
        Membership.objects.create(
            user=self.carol, organization=self.org_a, role=Membership.Role.MEMBER
        )

        self.project_a = make_project(self.org_a, "A public", False, self.alice, [self.alice])
        self.task_a = Task.objects.create(
            project=self.project_a, title="A task", created_by=self.alice, assignee=self.alice
        )
        self.project_b = make_project(self.org_b, "B public", False, self.bob, [self.bob])
        self.task_b = Task.objects.create(
            project=self.project_b, title="B task", created_by=self.bob, assignee=self.bob
        )
        self.hidden = make_project(self.org_a, "A secret", True, self.alice, [self.alice])
        self.task_hidden = Task.objects.create(
            project=self.hidden, title="Hidden task", created_by=self.alice, assignee=self.alice
        )
        for task, author in (
            (self.task_a, self.alice),
            (self.task_b, self.bob),
            (self.task_hidden, self.alice),
        ):
            Comment.objects.create(task=task, author=author, body="Hello")

    def ids(self, org, project, task):
        return {
            "org": org.pk,
            "project": project.pk,
            "task": task.pk,
            "membership": Membership.objects.filter(organization=org).order_by("pk").first().pk,
            "pm": ProjectMember.objects.filter(project=project).order_by("pk").first().pk,
            "comment": Comment.objects.filter(task=task).order_by("pk").first().pk,
        }

    def missing_ids(self, org_pk=MISSING):
        return {
            "org": org_pk,
            "project": MISSING,
            "task": MISSING,
            "membership": MISSING,
            "pm": MISSING,
            "comment": MISSING,
        }

    def call(self, user, method, url):
        self.client.force_authenticate(user)
        if method == "get":
            return self.client.get(url)
        return getattr(self.client, method)(url, BODY, format="json")

    def statuses(self, user, ids, endpoints):
        result = {}
        for name, keys in endpoints:
            url = reverse(name, args=[ids[key] for key in keys])
            for method in METHODS:
                result[(name, method)] = self.call(user, method, url).status_code
        return result

    def assert_indistinguishable(self, user, real_ids, missing_ids, endpoints):
        """A real-but-forbidden object must answer exactly like a missing one."""
        real = self.statuses(user, real_ids, endpoints)
        missing = self.statuses(user, missing_ids, endpoints)
        for key, status_code in real.items():
            with self.subTest(endpoint=key[0], method=key[1]):
                self.assertEqual(status_code, missing[key])
                self.assertFalse(200 <= status_code < 300)

    def foreign_case(self):
        ids = self.ids(self.org_b, self.project_b, self.task_b)
        return self.alice, ids, self.missing_ids(), ENDPOINTS

    def mixed_case(self):
        ids = {**self.ids(self.org_b, self.project_b, self.task_b), "org": self.org_a.pk}
        endpoints = [e for e in ENDPOINTS if len(e[1]) > 1]
        return self.alice, ids, self.missing_ids(self.org_a.pk), endpoints

    def hidden_case(self):
        ids = self.ids(self.org_a, self.hidden, self.task_hidden)
        endpoints = [e for e in ENDPOINTS if "project" in e[1]]
        return self.carol, ids, self.missing_ids(self.org_a.pk), endpoints

    def test_foreign_objects_look_like_missing_objects(self):
        self.assert_indistinguishable(*self.foreign_case())

    def test_own_organization_with_foreign_ids_looks_like_missing_objects(self):
        self.assert_indistinguishable(*self.mixed_case())

    def test_hidden_private_project_looks_like_missing_project(self):
        self.assert_indistinguishable(*self.hidden_case())

    def test_unauthenticated_requests_get_401_everywhere(self):
        ids = self.ids(self.org_a, self.project_a, self.task_a)
        for key, status_code in self.statuses(None, ids, ENDPOINTS).items():
            with self.subTest(endpoint=key[0], method=key[1]):
                self.assertEqual(status_code, 401)

    def test_probing_never_changes_data(self):
        before = snapshot()
        for user, ids, _missing, endpoints in (
            self.foreign_case(),
            self.mixed_case(),
            self.hidden_case(),
        ):
            self.statuses(user, ids, endpoints)
        self.assertEqual(snapshot(), before)
