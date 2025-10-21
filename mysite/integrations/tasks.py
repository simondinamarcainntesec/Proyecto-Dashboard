import os
import subprocess
import logging
from celery import shared_task
from datetime import datetime, timedelta
from pytz import timezone
import requests
from inyeccion_api.models import Alarm
from inyeccion_api.views import _map_api_alarm_to_model  # Ajusta según dónde esté
from integrations.alarmsone import list_alarms_all

# === Configuración de logging ===
log_file = os.path.join(os.path.dirname(__file__), '../../celery_run_log.txt')
logging.basicConfig(filename=log_file, level=logging.INFO, format='%(asctime)s - %(message)s')

TOKEN_FILE = os.path.join(os.path.dirname(__file__), '../../token.txt')
API_URL = "https://alarmsone.manageengine.com/rest/json/listAlarms"  # Endpoint correcto

# === Tarea para obtener el token ===
@shared_task
def tarea_obtener_token():
    try:
        logging.info("Inicio de obtención de token")
        result = subprocess.run(
            ["python3", os.path.join(os.path.dirname(__file__), "../../obtener_token.py")],
            capture_output=True,
            text=True,
            check=True
        )
        token = result.stdout.strip()

        with open(TOKEN_FILE, "w") as f:
            f.write(token)
        logging.info("Token actualizado correctamente")

    except subprocess.CalledProcessError as e:
        logging.error(f"Error al ejecutar obtener_token.py: {e}")
    except Exception as e:
        logging.exception(f"Error inesperado al obtener token: {e}")

# === Tarea de ingesta usando _map_api_alarm_to_model ===
TOKEN_FILE = os.path.join(os.path.dirname(__file__), '../../token.txt')

def _list_alarms_with_token(from_dt, to_dt, token, page_size=200, max_pages=50):
    """
    Wrapper de list_alarms_all que inyecta el token directamente.
    """
    import integrations.alarmsone as alarmsone
    original_token_func = alarmsone._token
    try:
        # Sobrescribir temporalmente la función _token para devolver nuestro token
        alarmsone._token = lambda: token
        return alarmsone.list_alarms_all(from_dt=from_dt, to_dt=to_dt, page_size=page_size, max_pages=max_pages)
    finally:
        # Restaurar la función original
        alarmsone._token = original_token_func

@shared_task
def tarea_ingesta_api():
    try:
        logging.info("Inicio de ingesta de API")

        # Leer token actualizado
        if not os.path.exists(TOKEN_FILE):
            logging.error("No se encontró token.txt")
            return
        with open(TOKEN_FILE, "r") as f:
            API_TOKEN = f.read().strip()

        tz = timezone("America/Santiago")
        now = datetime.now(tz)
        from_dt = now - timedelta(days=7)
        to_dt = now

        # Traer todas las alarmas usando wrapper con token
        result = _list_alarms_with_token(from_dt=from_dt, to_dt=to_dt, token=API_TOKEN)
        alarms_data = result.get("alarms", [])
        logging.info(f"Se recibieron {len(alarms_data)} alarmas de la API")

        if not alarms_data:
            return

        count_inserted = 0
        for item in alarms_data:
            alarm_obj = _map_api_alarm_to_model(item)
            if not alarm_obj:
                continue

            if Alarm.objects.filter(alertid=alarm_obj.alertid).exists():
                continue

            alarm_obj.save()
            count_inserted += 1

        logging.info(f"Ingesta finalizada. Nuevas filas insertadas: {count_inserted}")

    except Exception as e:
            logging.exception(f"Error inesperado durante la ingesta de API: {e}")
            
@shared_task
def ingesta_mensual_ciclica():
    """
    Ingresa datos históricos del mes dividiendo en tramos de 5 días.
    """
    try:
        logging.info("Inicio de ingesta histórica mensual")

        # Leer token actualizado
        if not os.path.exists(TOKEN_FILE):
            logging.error("No se encontró token.txt")
            return
        with open(TOKEN_FILE, "r") as f:
            API_TOKEN = f.read().strip()

        tz = timezone("America/Santiago")
        today = datetime.now(tz)
        # Empezamos 30 días atrás
        start_date = today - timedelta(days=30)
        end_date = start_date + timedelta(days=5)

        total_inserted = 0

        while start_date < today:
            logging.info(f"Traer alarmas desde {start_date} hasta {end_date}")

            result = _list_alarms_with_token(from_dt=start_date, to_dt=end_date, token=API_TOKEN)
            alarms_data = result.get("alarms", [])
            logging.info(f"Se recibieron {len(alarms_data)} alarmas de la API")

            count_inserted = 0
            for item in alarms_data:
                alarm_obj = _map_api_alarm_to_model(item)
                if not alarm_obj:
                    continue
                if Alarm.objects.filter(alertid=alarm_obj.alertid).exists():
                    continue
                alarm_obj.save()
                count_inserted += 1

            logging.info(f"Nuevas filas insertadas en este tramo: {count_inserted}")
            total_inserted += count_inserted

            # Avanzar el rango de 5 días
            start_date = end_date
            end_date = min(end_date + timedelta(days=5), today)

        logging.info(f"Ingesta histórica finalizada. Total filas insertadas: {total_inserted}")

    except Exception as e:
        logging.exception(f"Error inesperado durante la ingesta histórica: {e}")