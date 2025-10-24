import os
from celery import Celery
from celery.schedules import crontab

# Configura el módulo de settings de Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mysite.settings")

# Crea la aplicación Celery
app = Celery("mysite")

# Carga la configuración desde settings.py (usando prefijo CELERY_)
app.config_from_object("django.conf:settings", namespace="CELERY")

# Descubre automáticamente tareas en todas las apps registradas
app.autodiscover_tasks()


# === Programador de tareas (Celery Beat) ===
app.conf.beat_schedule = {
    # Obtención del token cada hora
    "obtener-token-cada-hora": {
        "task": "integrations.tasks.tarea_obtener_token",
        "schedule": crontab(minute='0'),  # cada hora exacta
    },
    # Ingesta de alarmas cada 65 minutos
    "ingesta-api-cada-65-min": {
        "task": "integrations.tasks.tarea_ingesta_api",
        "schedule": crontab(minute="5", hour="*/1"),  # cada hora, en el minuto 5
},
}
#    "ingesta-mensual": {
#        "task": "integrations.tasks.ingesta_mensual_ciclica",
#        "schedule": crontab(minute='0'),  # Cada hora exacta
#    }


# Configuración adicional
app.conf.timezone = "America/Santiago"
app.conf.task_default_queue = "default"
app.conf.worker_prefetch_multiplier = 1
app.conf.task_acks_late = True


@app.task(bind=True)
def debug_task(self):
    print(f"Request: {self.request!r}")
