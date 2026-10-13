import os

os.environ.setdefault("DJANGO_SECRET_KEY", "isolated-tests-only-" * 4)

from .settings import *  # noqa: F403
from .settings import DATABASES as BASE_DATABASES

SECRET_KEY = "isolated-tests-only-" * 4
ALLOWED_HOSTS = ["testserver", "localhost", "127.0.0.1"]
SECURE_SSL_REDIRECT = False
DATABASES = {
    **BASE_DATABASES,
    "default": {"ENGINE": "django.db.backends.sqlite3", "NAME": "/tmp/server-manages-tests.sqlite", "TEST": {"NAME": "/tmp/server-manages-tests-test.sqlite"}, "OPTIONS": {"timeout": 5, "transaction_mode": "IMMEDIATE"}, "ATOMIC_REQUESTS": False, "CONN_MAX_AGE": 0},
    "control": {"ENGINE": "django.db.backends.sqlite3", "NAME": "/tmp/server-manages-control-tests.sqlite", "TEST": {"NAME": "/tmp/server-manages-control-tests-test.sqlite"}, "OPTIONS": {"timeout": 5, "transaction_mode": "IMMEDIATE"}, "ATOMIC_REQUESTS": False, "CONN_MAX_AGE": 0},
}
