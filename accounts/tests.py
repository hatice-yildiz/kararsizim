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

    def test_login_with_username(self):
        r = self.client.post(reverse("login"), {"username": "ali", "password": "GucluSifre#2026"})
        self.assertRedirects(r, "/")
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.user.pk)

    def test_login_with_username_is_case_insensitive(self):
        r = self.client.post(reverse("login"), {"username": "ALi", "password": "GucluSifre#2026"})
        self.assertRedirects(r, "/")

    def test_login_with_username_wrong_password(self):
        r = self.client.post(reverse("login"), {"username": "ali", "password": "yanlis"})
        self.assertContains(r, "E-posta/kullanıcı adı veya parola hatalı.")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_login_unknown_identifier(self):
        for ident in ["yok", "yok@example.com"]:
            r = self.client.post(reverse("login"), {"username": ident, "password": "GucluSifre#2026"})
            self.assertContains(r, "E-posta/kullanıcı adı veya parola hatalı.")

    def test_value_with_at_sign_is_never_looked_up_as_username(self):
        # "@" içeren değer her zaman e-posta olarak aranır, kullanıcı adı olarak değil
        r = self.client.post(reverse("login"), {"username": "ali@", "password": "GucluSifre#2026"})
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_wrong_password(self):
        r = self.client.post(reverse("login"), {"username": "ali@example.com", "password": "yanlis"})
        self.assertContains(r, "E-posta/kullanıcı adı veya parola hatalı.")

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


class SingleRegistrationFlowTests(TestCase):
    """Bir kullanıcı yalnızca bir kez kayıt olur; sonra çıkış/giriş yapabilir ve oturumu kalır."""

    data = {"username": "ayse_01", "email": "ayse@example.com", "password1": "GucluSifre#2026", "password2": "GucluSifre#2026"}

    def test_register_once_then_logout_and_login_with_email_without_registering_again(self):
        self.client.post(reverse("register"), self.data)
        self.assertEqual(User.objects.count(), 1)

        # Kayıttan sonra oturum açık kalır: korumalı sayfaya girişsiz erişilir
        self.assertEqual(self.client.get("/anket/yeni/").status_code, 200)
        self.assertEqual(self.client.get("/anketlerim/").status_code, 200)

        # Çıkış yap, sonra yeniden KAYIT OLMADAN e-posta + parola ile giriş yap
        self.client.post(reverse("logout"))
        self.assertRedirects(self.client.get("/anket/yeni/"), "/giris/?next=/anket/yeni/")
        r = self.client.post(reverse("login"), {"username": "ayse@example.com", "password": "GucluSifre#2026"})
        self.assertRedirects(r, "/")
        self.assertEqual(self.client.get("/anket/yeni/").status_code, 200)
        self.assertEqual(User.objects.count(), 1)

    def test_second_registration_with_same_details_is_rejected_not_duplicated(self):
        self.client.post(reverse("register"), self.data)
        self.client.post(reverse("logout"))
        r = self.client.post(reverse("register"), self.data)
        self.assertContains(r, "Bu kullanıcı adı zaten alınmış.")
        self.assertContains(r, "Bu e-posta adresi zaten kayıtlı.")
        self.assertEqual(User.objects.count(), 1)

    def test_login_is_case_insensitive_on_email(self):
        self.client.post(reverse("register"), self.data)
        self.client.post(reverse("logout"))
        r = self.client.post(reverse("login"), {"username": "AYSE@Example.COM", "password": "GucluSifre#2026"})
        self.assertRedirects(r, "/")
