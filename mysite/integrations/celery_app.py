from celery import Celery
from celery.schedules import crontab
from datetime import timedelta
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mysite.settings")

app = Celery("integrations")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

# Zona horaria
app.conf.timezone = "America/Santiago"
app.conf.enable_utc = False

# === Programación de tareas ===
app.conf.beat_schedule = {
    "obtener-token-cada-hora": {
        "task": "integrations.tasks.tarea_obtener_token",
        "schedule": crontab(minute="*"),  # cada hora en punto
    },
    "ingesta-api-cada-hora": {
        "task": "integrations.tasks.tarea_ingesta_api",
        "schedule": timedelta(hours=1),
    },
}
