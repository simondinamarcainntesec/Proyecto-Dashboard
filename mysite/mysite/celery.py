import os
from celery import Celery
from celery.schedules import crontab

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mysite.settings')

# Crear app
app = Celery('mysite')

# Configuración usando settings de Django
app.config_from_object('django.conf:settings', namespace='CELERY')

# Autodescubrir tareas
app.autodiscover_tasks()

# Programación de tareas: fuente de verdad centralizada aquí.
app.conf.beat_schedule = {
    "obtener-token-every-hour": {
        "task": "integrations.tasks.tarea_obtener_token",
        "schedule": crontab(minute=0),  # cada hora en el minuto 0
    },
    "ingesta-api-every-30min": {
        "task": "integrations.tasks.tarea_ingesta_api",
        "schedule": crontab(minute='*/30'),  # cada 30 minutos
    },
}