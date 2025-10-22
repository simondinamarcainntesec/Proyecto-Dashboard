from celery import Celery
from celery.schedules import crontab
from datetime import timedelta
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mysite.settings")

app = Celery("mysite")  # más coherente con tu proyecto Django
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

app.conf.timezone = "America/Santiago"
app.conf.enable_utc = False

# === Programación de tareas automáticas ===
app.conf.beat_schedule = {
    "obtener-token-cada-5-minutos": {
        "task": "integrations.tasks.tarea_obtener_token",
        "schedule": crontab(minute="*/5"),  # cada 5 minutos
    },
    "ingesta-api-cada-5-minutos": {
        "task": "integrations.tasks.tarea_ingesta_api",
        "schedule": crontab(minute="*/5"),  # cada 5 minutos
    },
}
