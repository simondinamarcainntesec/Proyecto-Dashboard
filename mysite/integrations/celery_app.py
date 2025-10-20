from celery import Celery
from celery.schedules import crontab
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mysite.settings")

app = Celery("integrations")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

# === Configuración de zona horaria ===
app.conf.timezone = "America/Santiago"
app.conf.enable_utc = False  # importante para respetar la zona local

# === Programación: ejecutar cada hora en el minuto 0 ===
app.conf.beat_schedule = {
    "obtener-token-cada-hora": {
        "task": "integrations.tasks.tarea_obtener_token",
        "schedule": crontab(minute="0"),  # cada hora
    },
}
