# integrations/views.py
from django.shortcuts import render
from django.http import JsonResponse
from django.utils.timezone import now
from datetime import timedelta
import logging, os
from inyeccion_api.models import Alarm
from inyeccion_api.utils import _map_api_alarm_to_model  # Usa tus funciones existentes
import pathlib
from integrations.alarmsone import list_alarms_all

BASE_DIR = pathlib.Path(__file__).resolve().parent.parent.parent  # Sube hasta Proyecto-Dashboard/
TOKEN_FILE = BASE_DIR / "token.txt"
 # ajusta la ruta según tu proyecto

def obtener_alarmas_desde_api(request):
    """
    Obtiene las alarmas desde la API y las guarda en la base de datos.
    Se ejecuta solo al ingresar a la página o presionar "Refresh".
    """
    try:
        logging.info("Ejecutando ingesta manual de API")

        # Leer token
        if not os.path.exists(TOKEN_FILE):
            return JsonResponse({"error": "No se encontró token.txt"}, status=400)

        with open(TOKEN_FILE, "r") as f:
            API_TOKEN = f.read().strip()

        from_dt = now() - timedelta(days=7)
        to_dt = now()

        result = list_alarms_all(
        from_dt=int(from_dt.timestamp() * 1000),
        to_dt=int(to_dt.timestamp() * 1000),
        token=API_TOKEN
)
        alarms_data = result.get("alarms", []) if result else []

        count_inserted = 0
        for item in alarms_data:
            alarm_obj = _map_api_alarm_to_model(item)
            if not alarm_obj:
                continue
            if Alarm.objects.filter(alertid=alarm_obj.alertid).exists():
                continue
            alarm_obj.save()
            count_inserted += 1

        return JsonResponse({
            "status": "ok",
            "nuevas_alarmas": count_inserted,
            "total_recibidas": len(alarms_data)
        })

    except Exception as e:
        logging.exception(f"Error durante la ingesta manual: {e}")
        return JsonResponse({"error": str(e)}, status=500)
