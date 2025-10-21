# mysite/inyeccion_api/api_ingesta.py

import requests
from django.db import transaction
from inyeccion_api.models import Alarm  # o el nombre real de tu modelo
from datetime import datetime
import pytz

tz = pytz.timezone("America/Santiago")

API_URL = os.getenv("ALARMSONE_BASE_URL", "https://alarmsone.manageengine.com/rest/json")  # cambia esto por tu endpoint real


def obtener_datos_api():
    """Obtiene datos desde la API remota"""
    response = requests.get(API_URL, timeout=20)
    response.raise_for_status()
    return response.json()


@transaction.atomic
def insertar_alarmas():
    """Inserta solo alarmas nuevas y registra logs"""
    data = obtener_datos_api()
    nuevas = 0

    for item in data:
        alarma_id = item.get("id")

        # Evita duplicados
        if not Alarm.objects.filter(id=alarma_id).exists():
            Alarm.objects.create(
                id=alarma_id,
                msg_severity=item.get("msg_severity"),
                device_name=item.get("device_name"),
                msg=item.get("msg"),
                timestamp=item.get("timestamp"),
            )
            nuevas += 1

    # Registrar log de ejecución
    with open("celery_ingesta_log.txt", "a") as log:
        log.write(f"[{datetime.now(tz).strftime('%Y-%m-%d %H:%M:%S')}] Insertadas {nuevas} filas nuevas\n")

    return nuevas
