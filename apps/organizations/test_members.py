from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import User

from .models import Membership
from .services import create_organization

PASSWORD = "Tf-Demo-2026-x9"


def make_user(email):
    return User.objects.create_user(email=email, password=PASSWORD)


class MembershipApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = make_user("admin@example.com")
        self.org = create_organization(user=self.admin, name="Acme")
        self.admin_ms = Membership.objects.get(user=self.admin, organization=self.org)
        self.member = make_user("member@example.com")
        self.member_ms = Membership.objects.create(
            user=self.member, organization=self.org, role=Membership.Role.MEMBER
        )
        self.outsider = make_user("outsider@example.com")
        self.list_url = reverse("organizations:membership-list", args=[self.org.pk])

    def detail_url(self, membership, org=None):
        org = org or self.org
        return reverse("organizations:membership-detail", args=[org.pk, membership.pk])

    def test_requires_authentication(self):
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_non_member_gets_404_on_list(self):
        self.client.force_authenticate(self.outsider)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_non_member_gets_404_on_add(self):
        self.client.force_authenticate(self.outsider)
        response = self.client.post(
            self.list_url, {"email": self.outsider.email}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertFalse(
            Membership.objects.filter(user=self.outsider, organization=self.org).exists()
        )

    def test_member_can_list_members(self):
        self.client.force_authenticate(self.member)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        emails = sorted(item["email"] for item in response.data["results"])
        self.assertEqual(emails, ["admin@example.com", "member@example.com"])

    def test_member_cannot_add_change_or_remove(self):
        self.client.force_authenticate(self.member)
        add = self.client.post(self.list_url, {"email": self.outsider.email}, format="json")
        change = self.client.patch(
            self.detail_url(self.admin_ms), {"role": "member"}, format="json"
        )
        remove = self.client.delete(self.detail_url(self.admin_ms))
        self.assertEqual(add.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(change.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(remove.status_code, status.HTTP_403_FORBIDDEN)
        self.admin_ms.refresh_from_db()
        self.assertEqual(self.admin_ms.role, Membership.Role.ADMIN)

    def test_admin_can_add_member_by_email(self):
        self.client.force_authenticate(self.admin)
        response = self.client.post(
            self.list_url, {"email": "OUTSIDER@Example.com"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["role"], "member")
        self.assertTrue(
            Membership.objects.filter(user=self.outsider, organization=self.org).exists()
        )

    def test_add_unknown_email_is_rejected(self):
        self.client.force_authenticate(self.admin)
        response = self.client.post(
            self.list_url, {"email": "nobody@example.com"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.data)

    def test_add_existing_member_is_rejected(self):
        self.client.force_authenticate(self.admin)
        response = self.client.post(
            self.list_url, {"email": self.member.email}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.data)

    def test_add_with_invalid_role_is_rejected(self):
        self.client.force_authenticate(self.admin)
        response = self.client.post(
            self.list_url,
            {"email": self.outsider.email, "role": "superuser"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("role", response.data)

    def test_admin_can_change_role_and_other_fields_are_ignored(self):
        self.client.force_authenticate(self.admin)
        payload = {"role": "team_lead", "user": self.outsider.pk}
        response = self.client.patch(self.detail_url(self.member_ms), payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.member_ms.refresh_from_db()
        self.assertEqual(self.member_ms.role, Membership.Role.TEAM_LEAD)
        self.assertEqual(self.member_ms.user, self.member)

    def test_cannot_demote_last_admin(self):
        self.client.force_authenticate(self.admin)
        response = self.client.patch(
            self.detail_url(self.admin_ms), {"role": "member"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.admin_ms.refresh_from_db()
        self.assertEqual(self.admin_ms.role, Membership.Role.ADMIN)

    def test_can_demote_admin_when_another_admin_exists(self):
        self.member_ms.role = Membership.Role.ADMIN
        self.member_ms.save()
        self.client.force_authenticate(self.admin)
        response = self.client.patch(
            self.detail_url(self.admin_ms), {"role": "member"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.admin_ms.refresh_from_db()
        self.assertEqual(self.admin_ms.role, Membership.Role.MEMBER)

    def test_cannot_remove_last_admin(self):
        self.client.force_authenticate(self.admin)
        response = self.client.delete(self.detail_url(self.admin_ms))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(Membership.objects.filter(pk=self.admin_ms.pk).exists())

    def test_admin_can_remove_member_and_member_loses_access(self):
        self.client.force_authenticate(self.admin)
        response = self.client.delete(self.detail_url(self.member_ms))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Membership.objects.filter(pk=self.member_ms.pk).exists())
        self.client.force_authenticate(self.member)
        after = self.client.get(self.list_url)
        self.assertEqual(after.status_code, status.HTTP_404_NOT_FOUND)

    def test_cannot_touch_membership_of_another_organization(self):
        other_org = create_organization(user=self.outsider, name="Other Org")
        other_ms = Membership.objects.get(user=self.outsider, organization=other_org)
        self.client.force_authenticate(self.admin)
        change = self.client.patch(
            self.detail_url(other_ms), {"role": "member"}, format="json"
        )
        remove = self.client.delete(self.detail_url(other_ms))
        self.assertEqual(change.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(remove.status_code, status.HTTP_404_NOT_FOUND)
        other_ms.refresh_from_db()
        self.assertEqual(other_ms.role, Membership.Role.ADMIN)
