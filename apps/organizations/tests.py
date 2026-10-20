from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.accounts.models import User

from .models import Membership, Organization
from .services import create_organization


class OrganizationServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="owner@example.com", password="Tf-Demo-2026-x9"
        )

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
