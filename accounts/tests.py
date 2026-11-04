from django.contrib.auth import authenticate, get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase

User = get_user_model()


class UserModelTests(TestCase):
    def test_email_lowercased_and_login_with_email(self):
        User.objects.create_user(username="ali", email="Ali@Example.com", password="Sifre12345!")
        self.assertEqual(User.objects.get().email, "ali@example.com")
        self.assertIsNotNone(authenticate(username="ALI@example.COM", password="Sifre12345!"))
        self.assertIsNone(authenticate(username="ali@example.com", password="yanlis"))

    def test_username_unique_case_insensitive(self):
        User.objects.create_user(username="Ali", email="a@example.com", password="x")
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.create_user(username="ali", email="b@example.com", password="x")

    def test_email_unique_case_insensitive(self):
        User.objects.create_user(username="ali", email="a@example.com", password="x")
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.create_user(username="veli", email="A@example.com", password="x")


class HomeTests(TestCase):
    def test_home_opens(self):
        r = self.client.get("/")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Kararsızım")


from django.urls import reverse


class RegisterTests(TestCase):
    data = {"username": "ali_01", "email": "Ali@Example.com", "password1": "GucluSifre#2026", "password2": "GucluSifre#2026"}

    def test_register_logs_in_and_redirects_home(self):
        r = self.client.post(reverse("register"), self.data)
        self.assertRedirects(r, "/")
        self.assertEqual(int(self.client.session["_auth_user_id"]), User.objects.get().pk)
        self.assertEqual(User.objects.get().email, "ali@example.com")

    def test_duplicate_email_rejected_case_insensitive(self):
        User.objects.create_user(username="x", email="ali@example.com", password="p")
        r = self.client.post(reverse("register"), self.data)
        self.assertContains(r, "Bu e-posta adresi zaten kayıtlı.")
        self.assertEqual(User.objects.count(), 1)

    def test_duplicate_username_rejected_case_insensitive(self):
        User.objects.create_user(username="ALI_01", email="other@example.com", password="p")
        r = self.client.post(reverse("register"), self.data)
        self.assertContains(r, "Bu kullanıcı adı zaten alınmış.")
        self.assertEqual(User.objects.count(), 1)

    def test_username_rules(self):
        for bad in ["ab", "a" * 21, "ali veli", "ali-veli", "ali@x"]:
            r = self.client.post(reverse("register"), {**self.data, "username": bad})
            self.assertEqual(User.objects.count(), 0, bad)
            self.assertEqual(r.status_code, 200)

    def test_password_mismatch(self):
        r = self.client.post(reverse("register"), {**self.data, "password2": "baska"})
        self.assertContains(r, "Parolalar eşleşmiyor.")
        self.assertEqual(User.objects.count(), 0)

    def test_authenticated_user_redirected_from_register(self):
        u = User.objects.create_user(username="ali", email="a@example.com", password="p")
        self.client.force_login(u)
        self.assertRedirects(self.client.get(reverse("register")), "/")


class LoginLogoutTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="ali", email="ali@example.com", password="GucluSifre#2026")

    def test_login_with_email(self):
        r = self.client.post(reverse("login"), {"username": "ALI@example.com", "password": "GucluSifre#2026"})
        self.assertRedirects(r, "/")

    def test_login_with_username_fails(self):
        r = self.client.post(reverse("login"), {"username": "ali", "password": "GucluSifre#2026"})
        self.assertEqual(r.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_wrong_password(self):
        r = self.client.post(reverse("login"), {"username": "ali@example.com", "password": "yanlis"})
        self.assertContains(r, "E-posta veya parola hatalı.")

    def test_login_redirects_to_next(self):
        r = self.client.post(reverse("login") + "?next=/anketlerim/", {"username": "ali@example.com", "password": "GucluSifre#2026", "next": "/anketlerim/"})
        self.assertRedirects(r, "/anketlerim/", fetch_redirect_response=False)

    def test_logout_requires_post(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse("logout")).status_code, 405)
        self.assertIn("_auth_user_id", self.client.session)
        self.assertRedirects(self.client.post(reverse("logout")), "/")
        self.assertNotIn("_auth_user_id", self.client.session)


class NavbarAndPrivacyTests(TestCase):
    def test_guest_navbar(self):
        r = self.client.get("/")
        self.assertContains(r, "Kayıt Ol")
        self.assertContains(r, "Giriş")
        self.assertNotContains(r, "Çıkış")

    def test_user_navbar_shows_username_not_email(self):
        u = User.objects.create_user(username="ali", email="gizli@example.com", password="p")
        self.client.force_login(u)
        r = self.client.get("/")
        self.assertContains(r, "@ali")
        self.assertContains(r, "Anketlerim")
        self.assertContains(r, "Çıkış")
        self.assertNotContains(r, "gizli@example.com")
