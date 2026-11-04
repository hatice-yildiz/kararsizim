from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.password_validation import validate_password

from .models import username_validator

User = get_user_model()


class RegisterForm(forms.Form):
    username = forms.CharField(
        label="Kullanıcı adı",
        min_length=3,
        max_length=20,
        validators=[username_validator],
        help_text="3-20 karakter; harf, rakam, alt çizgi ve nokta.",
        error_messages={
            "required": "Kullanıcı adı zorunludur.",
            "min_length": "Kullanıcı adı en az 3 karakter olmalı.",
            "max_length": "Kullanıcı adı en fazla 20 karakter olabilir.",
        },
    )
    email = forms.EmailField(
        label="E-posta",
        error_messages={
            "required": "E-posta zorunludur.",
            "invalid": "Geçerli bir e-posta adresi gir.",
        },
    )
    password1 = forms.CharField(
        label="Parola",
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        error_messages={"required": "Parola zorunludur."},
    )
    password2 = forms.CharField(
        label="Parola (tekrar)",
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        error_messages={"required": "Parolayı tekrar gir."},
    )

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError("Bu kullanıcı adı zaten alınmış.")
        return username

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Bu e-posta adresi zaten kayıtlı.")
        return email

    def clean(self):
        cleaned = super().clean()
        p1, p2 = cleaned.get("password1"), cleaned.get("password2")
        if p1 and p2 and p1 != p2:
            self.add_error("password2", "Parolalar eşleşmiyor.")
        elif p1:
            try:
                validate_password(
                    p1, User(username=cleaned.get("username", ""), email=cleaned.get("email", ""))
                )
            except forms.ValidationError as e:
                self.add_error("password1", e)
        return cleaned

    def save(self):
        return User.objects.create_user(
            username=self.cleaned_data["username"],
            email=self.cleaned_data["email"],
            password=self.cleaned_data["password1"],
        )


class EmailLoginForm(AuthenticationForm):
    """E-posta ya da kullanıcı adı + parola ile giriş formu."""

    username = forms.CharField(
        label="E-posta veya kullanıcı adı",
        max_length=254,
        widget=forms.TextInput(attrs={"autofocus": True, "autocomplete": "username"}),
        error_messages={"required": "E-posta veya kullanıcı adı zorunludur."},
    )
    password = forms.CharField(
        label="Parola",
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
        error_messages={"required": "Parola zorunludur."},
    )
    error_messages = {
        "invalid_login": "E-posta/kullanıcı adı veya parola hatalı.",
        "inactive": "Bu hesap devre dışı.",
    }
