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


class ProjectMemberApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = make_user("admin@example.com")
        self.org = create_organization(user=self.admin, name="Acme")
        self.manager = make_user("manager@example.com")
        self.member = make_user("member@example.com")
        self.member2 = make_user("member2@example.com")
        self.outsider = make_user("outsider@example.com")
        add_to_org(self.org, self.manager, Membership.Role.MANAGER)
        add_to_org(self.org, self.member, Membership.Role.MEMBER)
        add_to_org(self.org, self.member2, Membership.Role.MEMBER)
        self.public = self.make_project("Public", False, [self.admin])
        self.secret = self.make_project("Secret", True, [self.admin, self.member])

    def make_project(self, name, is_private, members):
        project = Project.objects.create(
            organization=self.org,
            name=name,
            is_private=is_private,
            created_by=self.admin,
        )
        for user in members:
            ProjectMember.objects.create(project=project, user=user)
        return project

    def list_url(self, project):
        return reverse("projects:project-member-list", args=[self.org.pk, project.pk])

    def detail_url(self, project, project_member):
        return reverse(
            "projects:project-member-detail",
            args=[self.org.pk, project.pk, project_member.pk],
        )

    def test_requires_authentication(self):
        response = self.client.get(self.list_url(self.public))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_non_organization_member_gets_404(self):
        self.client.force_authenticate(self.outsider)
        response = self.client.get(self.list_url(self.public))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_member_can_list_members_of_public_project(self):
        self.client.force_authenticate(self.member)
        response = self.client.get(self.list_url(self.public))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual([m["email"] for m in response.data], ["admin@example.com"])

    def test_member_cannot_list_private_project_they_are_not_in(self):
        self.client.force_authenticate(self.member2)
        response = self.client.get(self.list_url(self.secret))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_org_admin_can_list_private_project_without_membership(self):
        hidden = self.make_project("Hidden", True, [self.member])
        self.client.force_authenticate(self.admin)
        response = self.client.get(self.list_url(hidden))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual([m["email"] for m in response.data], ["member@example.com"])

    def test_admin_adds_organization_member_by_email(self):
        self.client.force_authenticate(self.admin)
        response = self.client.post(
            self.list_url(self.public), {"email": "MEMBER@Example.com"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["email"], "member@example.com")
        self.assertTrue(
            ProjectMember.objects.filter(project=self.public, user=self.member).exists()
        )

    def test_manager_can_add_member(self):
        self.client.force_authenticate(self.manager)
        response = self.client.post(
            self.list_url(self.public), {"email": self.member2.email}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_regular_member_cannot_add(self):
        self.client.force_authenticate(self.member)
        response = self.client.post(
            self.list_url(self.public), {"email": self.member2.email}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(
            ProjectMember.objects.filter(project=self.public, user=self.member2).exists()
        )

    def test_cannot_add_user_outside_the_organization(self):
        self.client.force_authenticate(self.admin)
        outside = self.client.post(
            self.list_url(self.public), {"email": self.outsider.email}, format="json"
        )
        unknown = self.client.post(
            self.list_url(self.public), {"email": "nobody@example.com"}, format="json"
        )
        self.assertEqual(outside.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(unknown.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(outside.data, unknown.data)
        self.assertFalse(
            ProjectMember.objects.filter(project=self.public, user=self.outsider).exists()
        )

    def test_cannot_add_existing_project_member(self):
        self.client.force_authenticate(self.admin)
        response = self.client.post(
            self.list_url(self.public), {"email": self.admin.email}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(ProjectMember.objects.filter(project=self.public).count(), 1)

    def test_manager_not_in_private_project_gets_404_on_add(self):
        self.client.force_authenticate(self.manager)
        response = self.client.post(
            self.list_url(self.secret), {"email": self.member2.email}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertFalse(
            ProjectMember.objects.filter(project=self.secret, user=self.member2).exists()
        )

    def test_admin_can_remove_member(self):
        pm = ProjectMember.objects.get(project=self.secret, user=self.member)
        self.client.force_authenticate(self.admin)
        response = self.client.delete(self.detail_url(self.secret, pm))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(ProjectMember.objects.filter(pk=pm.pk).exists())

    def test_regular_member_cannot_remove(self):
        admin_pm = ProjectMember.objects.get(project=self.secret, user=self.admin)
        self.client.force_authenticate(self.member)
        response = self.client.delete(self.detail_url(self.secret, admin_pm))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(ProjectMember.objects.filter(pk=admin_pm.pk).exists())

    def test_member_id_from_another_project_returns_404(self):
        pm = ProjectMember.objects.get(project=self.secret, user=self.member)
        self.client.force_authenticate(self.admin)
        response = self.client.delete(self.detail_url(self.public, pm))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(ProjectMember.objects.filter(pk=pm.pk).exists())

    def test_removed_member_loses_access_to_private_project(self):
        pm = ProjectMember.objects.get(project=self.secret, user=self.member)
        self.client.force_authenticate(self.admin)
        self.client.delete(self.detail_url(self.secret, pm))
        self.client.force_authenticate(self.member)
        detail = reverse("projects:project-detail", args=[self.org.pk, self.secret.pk])
        response = self.client.get(detail)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
