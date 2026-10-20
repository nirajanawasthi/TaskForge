from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import User

from .models import Membership, Organization
from .services import create_organization

PASSWORD = "Tf-Demo-2026-x9"


def make_user(email):
    return User.objects.create_user(email=email, password=PASSWORD)


class OrganizationServiceTests(TestCase):
    def setUp(self):
        self.user = make_user("owner@example.com")

    def test_creator_becomes_admin_member(self):
        org = create_organization(user=self.user, name="Acme Inc")
        membership = Membership.objects.get(user=self.user, organization=org)
        self.assertEqual(membership.role, Membership.Role.ADMIN)
        self.assertEqual(org.created_by, self.user)

    def test_slug_is_generated_and_unique(self):
        first = create_organization(user=self.user, name="Acme Inc")
        second = create_organization(user=self.user, name="Acme Inc")
        self.assertEqual(first.slug, "acme-inc")
        self.assertEqual(second.slug, "acme-inc-2")

    def test_user_cannot_join_same_organization_twice(self):
        org = create_organization(user=self.user, name="Acme Inc")
        with self.assertRaises(IntegrityError), transaction.atomic():
            Membership.objects.create(user=self.user, organization=org)
        self.assertEqual(Membership.objects.filter(organization=org).count(), 1)


class OrganizationApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.alice = make_user("alice@example.com")
        self.bob = make_user("bob@example.com")
        self.list_url = reverse("organizations:organization-list")

    def detail_url(self, org):
        return reverse("organizations:organization-detail", args=[org.pk])

    def test_create_requires_authentication(self):
        response = self.client.post(self.list_url, {"name": "Acme"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_create_makes_creator_admin(self):
        self.client.force_authenticate(self.alice)
        response = self.client.post(self.list_url, {"name": "Acme"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["my_role"], "admin")
        org = Organization.objects.get(pk=response.data["id"])
        membership = Membership.objects.get(user=self.alice, organization=org)
        self.assertEqual(membership.role, Membership.Role.ADMIN)

    def test_create_ignores_slug_and_created_by_from_payload(self):
        self.client.force_authenticate(self.alice)
        payload = {"name": "Acme", "slug": "hacked", "created_by": self.bob.pk, "my_role": "member"}
        response = self.client.post(self.list_url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        org = Organization.objects.get(pk=response.data["id"])
        self.assertEqual(org.slug, "acme")
        self.assertEqual(org.created_by, self.alice)
        self.assertEqual(response.data["my_role"], "admin")

    def test_create_requires_name(self):
        self.client.force_authenticate(self.alice)
        response = self.client.post(self.list_url, {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("name", response.data)

    def test_list_requires_authentication(self):
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_list_shows_only_own_organizations(self):
        mine = create_organization(user=self.alice, name="Alice Org")
        create_organization(user=self.bob, name="Bob Org")
        self.client.force_authenticate(self.alice)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [item["id"] for item in response.data]
        self.assertEqual(ids, [mine.pk])

    def test_retrieve_own_organization(self):
        org = create_organization(user=self.alice, name="Alice Org")
        self.client.force_authenticate(self.alice)
        response = self.client.get(self.detail_url(org))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], "Alice Org")
        self.assertEqual(response.data["my_role"], "admin")

    def test_retrieve_other_organization_returns_404(self):
        org = create_organization(user=self.bob, name="Bob Org")
        self.client.force_authenticate(self.alice)
        response = self.client.get(self.detail_url(org))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_update_and_delete_are_not_allowed(self):
        org = create_organization(user=self.alice, name="Alice Org")
        self.client.force_authenticate(self.alice)
        patch = self.client.patch(self.detail_url(org), {"name": "X"}, format="json")
        delete = self.client.delete(self.detail_url(org))
        self.assertEqual(patch.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        self.assertEqual(delete.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        self.assertTrue(Organization.objects.filter(pk=org.pk).exists())
