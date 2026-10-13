from django.apps import AppConfig
from django.db.backends.signals import connection_created


class CommonConfig(AppConfig):
    name = "common"

    def ready(self):
        from .db import configure_django_connection

        connection_created.connect(configure_django_connection, dispatch_uid="common.sqlite_pragmas")
