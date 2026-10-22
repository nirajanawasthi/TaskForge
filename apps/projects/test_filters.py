from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.organizations.models import Membership
from apps.organizations.services import create_organization

from .models import Project, ProjectMember

PASSWORD = "Tf-Demo-2026-x9"


class ProjectFilterTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_user(email="admin@example.com", password=PASSWORD)
        self.org = create_organization(user=self.admin, name="Acme")
        self.member = User.objects.create_user(email="member@example.com", password=PASSWORD)
        Membership.objects.create(
            user=self.member, organization=self.org, role=Membership.Role.MEMBER
        )
        self.alpha = self.make_project("Alpha", False)
        self.beta = self.make_project("Beta", True)
        self.gamma = self.make_project("Gamma", False, description="billing service")
        self.url = reverse("projects:project-list", args=[self.org.pk])

    def make_project(self, name, is_private, description=""):
        project = Project.objects.create(
            organization=self.org,
            name=name,
            description=description,
            is_private=is_private,
            created_by=self.admin,
        )
        ProjectMember.objects.create(project=project, user=self.admin)
        return project

    def names(self, user, **params):
        self.client.force_authenticate(user)
        response = self.client.get(self.url, params)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        return [project["name"] for project in response.data["results"]]

    def test_list_is_paginated_and_ordered_by_name(self):
        self.client.force_authenticate(self.admin)
        response = self.client.get(self.url)
        self.assertEqual(
            set(response.data), {"count", "next", "previous", "results"}
        )
        self.assertEqual(response.data["count"], 3)
        self.assertEqual(self.names(self.admin), ["Alpha", "Beta", "Gamma"])

    def test_filter_by_is_private(self):
        self.assertEqual(self.names(self.admin, is_private="true"), ["Beta"])
        self.assertEqual(self.names(self.admin, is_private="false"), ["Alpha", "Gamma"])

    def test_search_matches_name_and_description(self):
        self.assertEqual(self.names(self.admin, search="alph"), ["Alpha"])
        self.assertEqual(self.names(self.admin, search="billing"), ["Gamma"])

    def test_ordering(self):
        self.assertEqual(
            self.names(self.admin, ordering="-name"), ["Gamma", "Beta", "Alpha"]
        )

    def test_filters_do_not_reveal_hidden_private_projects(self):
        self.assertEqual(self.names(self.member, is_private="true"), [])
        self.assertEqual(self.names(self.member, search="beta"), [])
        self.assertEqual(self.names(self.member), ["Alpha", "Gamma"])
