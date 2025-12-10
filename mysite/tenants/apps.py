# tenants/apps.py
from django.apps import AppConfig


class TenantsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "tenants"

    def ready(self):
        # Importa las señales para que se registren
        from . import signals  # noqa
