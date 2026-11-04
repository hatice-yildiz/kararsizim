from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend


class EmailBackend(ModelBackend):
    """E-posta ya da kullanıcı adı (ikisi de büyük/küçük harf duyarsız) + parola ile giriş.

    Kullanıcı adı `@` içeremediği için ("@" kuralı `username_validator`'da) bir değerin
    e-posta mı kullanıcı adı mı olduğu karışmaz.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        identifier = (username or kwargs.get("email") or "").strip()
        if not identifier or password is None:
            return None
        User = get_user_model()
        lookup = "email__iexact" if "@" in identifier else "username__iexact"
        user = User.objects.filter(**{lookup: identifier}).first()
        if user is None:
            User().set_password(password)  # zamanlama saldırılarını azalt
            return None
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
