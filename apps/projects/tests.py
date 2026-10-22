from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.organizations.models import Membership
from apps.organizations.services import create_organization

from .models import Project, ProjectMember

PASSWORD = "Tf-Demo-2026-x9"


def make_user(email):
    return User.objects.create_user(email=email, password=PASSWORD)


def add_to_org(org, user, role):
    return Membership.objects.create(user=user, organization=org, role=role)


class ProjectApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = make_user("admin@example.com")
        self.org = create_organization(user=self.admin, name="Acme")
        self.manager = make_user("manager@example.com")
        self.member = make_user("member@example.com")
        self.outsider = make_user("outsider@example.com")
        add_to_org(self.org, self.manager, Membership.Role.MANAGER)
        add_to_org(self.org, self.member, Membership.Role.MEMBER)
        self.list_url = reverse("projects:project-list", args=[self.org.pk])

    def detail_url(self, project, org=None):
        org = org or self.org
        return reverse("projects:project-detail", args=[org.pk, project.pk])

    def make_project(self, name="Alpha", is_private=False, members=()):
        project = Project.objects.create(
            organization=self.org,
            name=name,
            is_private=is_private,
            created_by=self.admin,
        )
        for user in members:
            ProjectMember.objects.create(project=project, user=user)
        return project

    def test_requires_authentication(self):
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_non_member_gets_404_on_list(self):
        self.client.force_authenticate(self.outsider)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_non_member_gets_404_on_create(self):
        self.client.force_authenticate(self.outsider)
        response = self.client.post(self.list_url, {"name": "Sneaky"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertFalse(Project.objects.filter(name="Sneaky").exists())

    def test_admin_creates_project_and_becomes_project_member(self):
        self.client.force_authenticate(self.admin)
        response = self.client.post(
            self.list_url, {"name": "Alpha", "description": "First"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["created_by"], "admin@example.com")
        project = Project.objects.get(pk=response.data["id"])
        self.assertEqual(project.organization, self.org)
        self.assertTrue(
            ProjectMember.objects.filter(project=project, user=self.admin).exists()
        )

    def test_manager_can_create_project(self):
        self.client.force_authenticate(self.manager)
        response = self.client.post(self.list_url, {"name": "Beta"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_regular_member_cannot_create_project(self):
        self.client.force_authenticate(self.member)
        response = self.client.post(self.list_url, {"name": "Nope"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(Project.objects.filter(name="Nope").exists())

    def test_create_requires_name(self):
        self.client.force_authenticate(self.admin)
        response = self.client.post(self.list_url, {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("name", response.data)

    def test_member_sees_public_project(self):
        project = self.make_project(name="Public")
        self.client.force_authenticate(self.member)
        listing = self.client.get(self.list_url)
        detail = self.client.get(self.detail_url(project))
        self.assertEqual([p["id"] for p in listing.data["results"]], [project.pk])
        self.assertEqual(detail.status_code, status.HTTP_200_OK)

    def test_member_cannot_see_private_project_they_are_not_in(self):
        project = self.make_project(name="Secret", is_private=True, members=[self.admin])
        self.client.force_authenticate(self.member)
        listing = self.client.get(self.list_url)
        detail = self.client.get(self.detail_url(project))
        self.assertEqual(listing.data["results"], [])
        self.assertEqual(detail.status_code, status.HTTP_404_NOT_FOUND)

    def test_project_member_sees_private_project(self):
        project = self.make_project(
            name="Secret", is_private=True, members=[self.admin, self.member]
        )
        self.client.force_authenticate(self.member)
        listing = self.client.get(self.list_url)
        detail = self.client.get(self.detail_url(project))
        self.assertEqual([p["id"] for p in listing.data["results"]], [project.pk])
        self.assertEqual(detail.status_code, status.HTTP_200_OK)

    def test_org_admin_sees_private_project_without_membership(self):
        project = self.make_project(name="Secret", is_private=True, members=[self.member])
        self.client.force_authenticate(self.admin)
        detail = self.client.get(self.detail_url(project))
        self.assertEqual(detail.status_code, status.HTTP_200_OK)

    def test_manager_can_update_project_and_ignored_fields_stay_unchanged(self):
        project = self.make_project(name="Alpha")
        other_org = create_organization(user=self.outsider, name="Other Org")
        self.client.force_authenticate(self.manager)
        payload = {
            "name": "Renamed",
            "organization": other_org.pk,
            "created_by": self.outsider.pk,
        }
        response = self.client.patch(self.detail_url(project), payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        project.refresh_from_db()
        self.assertEqual(project.name, "Renamed")
        self.assertEqual(project.organization, self.org)
        self.assertEqual(project.created_by, self.admin)

    def test_regular_member_cannot_update_project(self):
        project = self.make_project(name="Alpha")
        self.client.force_authenticate(self.member)
        response = self.client.patch(self.detail_url(project), {"name": "X"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        project.refresh_from_db()
        self.assertEqual(project.name, "Alpha")

    def test_project_of_another_organization_returns_404(self):
        other_admin = make_user("other-admin@example.com")
        other_org = create_organization(user=other_admin, name="Other Org")
        foreign = Project.objects.create(
            organization=other_org, name="Foreign", created_by=other_admin
        )
        self.client.force_authenticate(self.admin)
        url = reverse("projects:project-detail", args=[self.org.pk, foreign.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_put_and_delete_are_not_allowed(self):
        project = self.make_project(name="Alpha")
        self.client.force_authenticate(self.admin)
        put = self.client.put(self.detail_url(project), {"name": "X"}, format="json")
        delete = self.client.delete(self.detail_url(project))
        self.assertEqual(put.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        self.assertEqual(delete.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        self.assertTrue(Project.objects.filter(pk=project.pk).exists())
