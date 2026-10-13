import os
import uuid
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent
DEBUG = os.environ.get("DJANGO_DEBUG", "0") == "1"


def _instance_id() -> str:
    configured = os.environ.get("INSTANCE_ID")
    instance_file = os.environ.get("INSTANCE_ID_FILE")
    value = configured
    if not value and instance_file:
        value = Path(instance_file).read_text(encoding="utf-8").strip()
    if not value:
        # Development and isolated tests use a deterministic identity. Deployments
        # should inject a persisted UUID through the environment or a secret file.
        return str(uuid.UUID(int=0))
    try:
        return str(uuid.UUID(value))
    except ValueError as exc:
        raise ImproperlyConfigured("INSTANCE_ID_INVALID") from exc


INSTANCE_ID = _instance_id()


def _secret_key() -> str:
    configured = os.environ.get("DJANGO_SECRET_KEY")
    secret_file = os.environ.get("DJANGO_SECRET_KEY_FILE")
    if configured:
        return configured
    if secret_file:
        return Path(secret_file).read_text(encoding="utf-8").strip()
    return ""


SECRET_KEY = _secret_key()
if not SECRET_KEY and not DEBUG:
    raise ImproperlyConfigured("DJANGO_SECRET_KEY_FILE_REQUIRED")
ALLOWED_HOSTS = [host for host in os.environ.get("ALLOWED_HOSTS", "").split(",") if host] or ["localhost"]
INSTALLED_APPS = [
    "django.contrib.auth", "django.contrib.contenttypes", "django.contrib.sessions", "django.contrib.staticfiles",
    "rest_framework", "common.apps.CommonConfig", "operations", "audit", "accounts", "assets",
]
AUTH_USER_MODEL = "accounts.User"
AUTHENTICATION_BACKENDS = ["accounts.backends.LocalBackend"]
ROOT_URLCONF = "config.urls"
MIDDLEWARE: list[str] = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "common.middleware.RequestSafetyMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "accounts.middleware.ForcePasswordChangeMiddleware",
]
TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [BASE_DIR / "templates"], "APP_DIRS": True,
    "OPTIONS": {"context_processors": ["django.template.context_processors.request"]},
}]
_data_root = Path(os.environ.get("DATA_ROOT", "/data"))
_business_db = os.environ.get("BUSINESS_DB", str(_data_root / "business.sqlite3"))
_control_db = os.environ.get("CONTROL_DB", str(_data_root / "control.sqlite3"))
_sqlite_options = {"timeout": 5, "transaction_mode": "IMMEDIATE"}
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3", "NAME": _business_db,
        "OPTIONS": _sqlite_options, "ATOMIC_REQUESTS": False, "CONN_MAX_AGE": 0,
    },
    "control": {
        "ENGINE": "django.db.backends.sqlite3", "NAME": _control_db,
        "OPTIONS": _sqlite_options.copy(), "ATOMIC_REQUESTS": False, "CONN_MAX_AGE": 0,
    },
}
DATABASE_ROUTERS = ["operations.router.ControlRouter"]
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "static-collected"
STATICFILES_DIRS = [BASE_DIR / "static"]
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
LANGUAGE_CODE = "zh-hans"
TIME_ZONE = "Asia/Shanghai"
USE_TZ = True
REST_FRAMEWORK = {"UNAUTHENTICATED_USER": None}
PASSWORD_HASHERS = ["django.contrib.auth.hashers.Argon2PasswordHasher"]
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SECURE = True
CSRF_COOKIE_SAMESITE = "Lax"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
DATA_UPLOAD_MAX_MEMORY_SIZE = 20 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 20 * 1024 * 1024
