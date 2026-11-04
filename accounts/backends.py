from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend


class EmailBackend(ModelBackend):
    """E-posta (büyük/küçük harf duyarsız) + parola ile giriş."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        email = (username or kwargs.get("email") or "").strip().lower()
        if not email or password is None:
            return None
        User = get_user_model()
        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            User().set_password(password)  # zamanlama saldırılarını azalt
            return None
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
