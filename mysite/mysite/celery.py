import os
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mysite.settings')

app = Celery('mysite')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

app.conf.beat_schedule = {
    "obtener-token-every-hour": {
        "task": "integrations.tasks.tarea_obtener_token",
        "schedule": crontab(minute='*'),  # cada hora
    },
    "ingesta-api-every-30min": {
        "task": "integrations.tasks.tarea_ingesta_api",
        "schedule": crontab(minute='*/30'),  # cada 30 minutos
    },
}
