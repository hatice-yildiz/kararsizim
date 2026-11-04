import os
import sys
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

import dj_database_url
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")

# Güvenli varsayılan: DEBUG yalnızca .env / ortam değişkeninde açıkça True verilirse açılır.
DEBUG = os.environ.get("DEBUG", "False").lower() in ("1", "true", "yes")

SECRET_KEY = os.environ.get("SECRET_KEY")
if not SECRET_KEY:
    if DEBUG or (len(sys.argv) > 1 and sys.argv[1] == "test"):
        SECRET_KEY = "dev-insecure-key-change-me"
    else:
        raise ImproperlyConfigured("SECRET_KEY ortam değişkeni tanımlı olmalı (DEBUG kapalıyken).")


def _csv(name, default=""):
    return [v.strip() for v in os.environ.get(name, default).split(",") if v.strip()]


ALLOWED_HOSTS = _csv("ALLOWED_HOSTS", "localhost,127.0.0.1")
CSRF_TRUSTED_ORIGINS = _csv("CSRF_TRUSTED_ORIGINS")

# Vercel'in sistem ortam değişkenlerinden (üretim alan adı, deployment ve dal adresleri)
# tam alan adlarını ekle; böylece joker (*.vercel.app) kullanmaya gerek kalmaz.
for _var in ("VERCEL_PROJECT_PRODUCTION_URL", "VERCEL_URL", "VERCEL_BRANCH_URL"):
    _host = os.environ.get(_var)
    if _host:
        ALLOWED_HOSTS.append(_host)
        CSRF_TRUSTED_ORIGINS.append(f"https://{_host}")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "accounts",
    "polls",
    "predictions",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# Database: DATABASE_URL (Supabase PostgreSQL) varsa onu, yoksa yerel SQLite kullan.
DATABASE_URL = os.environ.get("DATABASE_URL")
if DATABASE_URL:
    _db = dj_database_url.parse(DATABASE_URL, conn_max_age=0)  # serverless + transaction pooler
    # Uzak veritabanında (Supabase) SSL zorunlu; yalnızca yerel geliştirme/test PostgreSQL'inde atlanır.
    if _db.get("HOST") not in ("localhost", "127.0.0.1", "::1", ""):
        _db.setdefault("OPTIONS", {})["sslmode"] = "require"
    DATABASES = {"default": _db}
    # Supabase transaction pooler (port 6543) server-side cursor desteklemez
    DATABASES["default"]["DISABLE_SERVER_SIDE_CURSORS"] = True
    # psycopg3 hazır sorguları (prepared statements) pooler'ın transaction modunda sorun çıkarır
    DATABASES["default"].setdefault("OPTIONS", {})["prepare_threshold"] = None
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

AUTH_USER_MODEL = "accounts.User"
AUTHENTICATION_BACKENDS = ["accounts.backends.EmailBackend"]

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "tr"
TIME_ZONE = "Europe/Istanbul"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
# Vercel, STATIC_ROOT tanımlıysa build sırasında collectstatic'i kendisi çalıştırır ve
# dosyaları CDN'den sunar (WhiteNoise yalnızca yerelde devrede). Varsayılan depolama desteklenir.

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "/giris/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/"

if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
