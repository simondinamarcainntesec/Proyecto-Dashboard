import os
from celery import Celery
from celery.schedules import crontab
from celery.signals import worker_ready  # <<< NUEVO

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
        "schedule": crontab(minute="0"),  # cada hora exacta
    },

    # === Sync de empresas una vez al día ===
    "sync-empresas-diario": {
        "task": "integrations.tasks.tarea_sync_empresas",
        "schedule": crontab(minute="0", hour="3"),  # todos los días a las 03:00 AM
    },

    # === Sync de clientes (usuarios con empresa) una vez al día ===
    "sync-clientes-soporte-diario": {
        "task": "integrations.tasks.tarea_sync_clientes_soporte",
        "schedule": crontab(minute="10", hour="3"),  # todos los días a las 03:10 AM
    },

    # === Sync de user_groups Site24x7 → Client.site24x7_user_groups una vez al día ===
    "sync-site24x7-user-groups-diario": {
        "task": "integrations.tasks.tarea_sync_site24x7_user_groups",
        "schedule": crontab(minute="20", hour="3"),  # todos los días a las 03:20 AM
    },

    # Ingesta mensual cada 5 minutos (si la quieres periódica además del arranque)
    #"ingesta-mensual": {
    #    "task": "integrations.tasks.ingesta_mensual_ciclica",
    #    "schedule": crontab(minute="*/5"),  # Cada 5 minutos
    #},

    # Ingesta de alarmas cada 65 minutos (en realidad: cada hora, minuto 5)
    "ingesta-api-cada-65-min": {
        "task": "integrations.tasks.tarea_ingesta_api",
        "schedule": crontab(minute="5", hour="*/1"),  # cada hora, en el minuto 5
        # Si de verdad quieres cada 65 min, conviene usar timedelta(minutes=65)
    },
        # ✅ Recordatorio tickets 2 días antes del vencimiento
    "soar-ticket-reminder-due-soon-diario": {
        "task": "soar_tickets.tasks.send_due_soon_reminders",
        "schedule": crontab(minute="0", hour="9"),  # todos los días 09:00 CL
    },

}

# Configuración adicional
app.conf.timezone = "America/Santiago"
app.conf.task_default_queue = "default"
app.conf.worker_prefetch_multiplier = 1
app.conf.task_acks_late = True


@app.task(bind=True)
def debug_task(self):
    print(f"Request: {self.request!r}")


# === Ejecutar ingesta mensual al iniciar el worker ===
@worker_ready.connect
def at_worker_ready(sender, **kwargs):
    try:
        print("[CELERY STARTUP] Lanzando ingesta mensual y recordatorio de tickets...")
        sender.app.send_task("integrations.tasks.ingesta_mensual_ciclica")
        #sender.app.send_task("soar_tickets.tasks.send_due_soon_reminders")
    except Exception as exc:
        print(f"[CELERY STARTUP] Error: {exc!r}")

