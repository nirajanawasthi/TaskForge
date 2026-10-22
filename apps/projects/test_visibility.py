from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.organizations.models import Membership
from apps.organizations.services import create_organization

from .models import Project, ProjectMember

PASSWORD = "Tf-Demo-2026-x9"


class HiddenProjectLeakTests(TestCase):
    """Regular members must get 404, not 403, for projects they cannot see."""

    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_user(email="admin@example.com", password=PASSWORD)
        self.org = create_organization(user=self.admin, name="Acme")
        self.member = User.objects.create_user(email="member@example.com", password=PASSWORD)
        Membership.objects.create(
            user=self.member, organization=self.org, role=Membership.Role.MEMBER
        )
        self.secret = Project.objects.create(
            organization=self.org, name="Secret", is_private=True, created_by=self.admin
        )
        ProjectMember.objects.create(project=self.secret, user=self.admin)

    def test_patch_on_hidden_private_project_returns_404(self):
        self.client.force_authenticate(self.member)
        url = reverse("projects:project-detail", args=[self.org.pk, self.secret.pk])
        response = self.client.patch(url, {"name": "X"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.secret.refresh_from_db()
        self.assertEqual(self.secret.name, "Secret")

    def test_adding_member_to_hidden_private_project_returns_404(self):
        self.client.force_authenticate(self.member)
        url = reverse("projects:project-member-list", args=[self.org.pk, self.secret.pk])
        response = self.client.post(url, {"email": self.member.email}, format="json")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertFalse(
            ProjectMember.objects.filter(project=self.secret, user=self.member).exists()
        )
