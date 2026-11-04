from django.contrib.auth.models import AbstractUser, UserManager
from django.core.validators import RegexValidator
from django.db import models
from django.db.models.functions import Lower

username_validator = RegexValidator(
    regex=r"^[A-Za-z0-9_.]{3,20}$",
    message="Kullanıcı adı 3-20 karakter olmalı; yalnızca harf, rakam, alt çizgi ve nokta içerebilir.",
)


class User(AbstractUser):
    first_name = None
    last_name = None

    username = models.CharField(
        "kullanıcı adı",
        max_length=20,
        unique=True,
        validators=[username_validator],
        error_messages={"unique": "Bu kullanıcı adı zaten alınmış."},
    )
    email = models.EmailField(
        "e-posta",
        unique=True,
        error_messages={"unique": "Bu e-posta adresi zaten kayıtlı."},
    )

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    objects = UserManager()

    class Meta:
        constraints = [
            models.UniqueConstraint(Lower("username"), name="unique_username_ci"),
            models.UniqueConstraint(Lower("email"), name="unique_email_ci"),
        ]

    def save(self, *args, **kwargs):
        if self.email:
            self.email = self.email.strip().lower()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.username
