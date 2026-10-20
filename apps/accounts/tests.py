from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from .models import User

PASSWORD = "Tf-Demo-2026-x9"


def make_user(email="user@example.com", **extra):
    return User.objects.create_user(email=email, password=PASSWORD, **extra)


class UserModelTests(TestCase):
    def test_create_user_hashes_password_and_normalizes_domain(self):
        user = User.objects.create_user(email="A@EXAMPLE.com", password=PASSWORD)
        self.assertEqual(user.email, "A@example.com")
        self.assertNotEqual(user.password, PASSWORD)
        self.assertTrue(user.check_password(PASSWORD))
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)

    def test_create_user_requires_email(self):
        with self.assertRaises(ValueError):
            User.objects.create_user(email="", password=PASSWORD)

    def test_create_superuser_sets_flags(self):
        admin = User.objects.create_superuser(email="admin@example.com", password=PASSWORD)
        self.assertTrue(admin.is_staff)
        self.assertTrue(admin.is_superuser)


class RegisterTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = reverse("accounts:register")
        self.payload = {
            "email": "New@Example.com",
            "first_name": "New",
            "last_name": "User",
            "password": PASSWORD,
            "password2": PASSWORD,
        }

    def test_register_creates_user(self):
        response = self.client.post(self.url, self.payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertNotIn("password", response.data)
        self.assertEqual(response.data["email"], "new@example.com")
        self.assertTrue(User.objects.filter(email="new@example.com").exists())

    def test_duplicate_email_is_rejected_case_insensitively(self):
        make_user(email="new@example.com")
        response = self.client.post(self.url, self.payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.data)

    def test_password_mismatch_is_rejected(self):
        payload = {**self.payload, "password2": "Different-2026-x9"}
        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("password2", response.data)

    def test_weak_password_is_rejected(self):
        payload = {**self.payload, "password": "12345678", "password2": "12345678"}
        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("password", response.data)

    def test_staff_flags_in_payload_are_ignored(self):
        payload = {**self.payload, "is_staff": True, "is_superuser": True}
        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user = User.objects.get(email="new@example.com")
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)


class AuthTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = make_user()

    def login(self, password=PASSWORD):
        return self.client.post(
            reverse("accounts:login"),
            {"email": self.user.email, "password": password},
            format="json",
        )

    def test_login_returns_tokens(self):
        response = self.login()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)

    def test_login_with_wrong_password_is_rejected(self):
        response = self.login(password="Wrong-Password-1")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_refresh_returns_new_access_token(self):
        refresh = self.login().data["refresh"]
        response = self.client.post(
            reverse("accounts:token_refresh"), {"refresh": refresh}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)


class MeTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = reverse("accounts:me")
        self.user = make_user(first_name="Test")

    def test_requires_authentication(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_get_returns_own_profile(self):
        self.client.force_authenticate(self.user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["email"], self.user.email)

    def test_patch_updates_name(self):
        self.client.force_authenticate(self.user)
        response = self.client.patch(self.url, {"first_name": "Updated"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "Updated")

    def test_patch_cannot_change_email_or_staff_flags(self):
        self.client.force_authenticate(self.user)
        payload = {"email": "hacker@example.com", "is_staff": True, "is_superuser": True}
        response = self.client.patch(self.url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "user@example.com")
        self.assertFalse(self.user.is_staff)
        self.assertFalse(self.user.is_superuser)

    def test_put_is_not_allowed(self):
        self.client.force_authenticate(self.user)
        response = self.client.put(self.url, {"first_name": "X"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_user_only_sees_own_profile(self):
        other = make_user(email="other@example.com", first_name="Other")
        self.client.force_authenticate(self.user)
        response = self.client.get(self.url)
        self.assertEqual(response.data["email"], self.user.email)
        self.assertNotEqual(response.data["id"], other.id)
