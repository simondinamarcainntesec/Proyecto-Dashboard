from datetime import datetime, timedelta, timezone as dt_timezone
from pytz import timezone as pytz_timezone
import logging, os, httpx
from celery import shared_task
from django.conf import settings
from pathlib import Path
from inyeccion_api.models import Alarm
from integrations.alarmsone import obtener_token_via_script, get_token
from inyeccion_api.utils import _map_api_alarm_to_model

TOKEN_FILE = Path(settings.BASE_DIR) / "token.txt"


# === Tarea 1: Obtener Token ===
@shared_task(bind=True, max_retries=3, default_retry_delay=10)
def tarea_obtener_token(self):
    """
    Tarea que obtiene un token desde la API y lo guarda en archivo.
    """
    try:
        logging.info("🔑 Solicitando nuevo token desde la API...")
        token = obtener_token_via_script()  # Usamos la función del módulo alarmsone

        if not token:
            raise ValueError("No se recibió token desde la API")

        # Guardar token en archivo
        with open(TOKEN_FILE, "w") as f:
            f.write(token)

        logging.info("✅ Token guardado correctamente.")
        return token

    except Exception as e:
        logging.error(f"❌ Error al obtener token: {e}")
        raise self.retry(exc=e)


# === Tarea 2: Ingesta API ===
@shared_task
def tarea_ingesta_api():
    """
    Ingresa las alarmas del día actual (desde 00:00 hasta ahora),
    paginando en bloques de 200 hasta un máximo de 10.000 alarmas.
    """
    try:
        logging.info("🚀 Inicio de ingesta diaria de API")

        tz = pytz_timezone("America/Santiago")
        now = datetime.now(tz)

        # Eliminar alarmas con más de un mes
        limite = now - timedelta(days=60)
        eliminadas, _ = Alarm.objects.filter(event_time__lt=limite).delete()
        logging.info(f"🧹 Alarmas antiguas eliminadas: {eliminadas}")

        # Calcular rango de hoy (00:00 → ahora)
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)

        # Convertir a UTC (API usa UTC)
        from_utc = start_of_day.astimezone(dt_timezone.utc)
        to_utc = now.astimezone(dt_timezone.utc)
        from_ms = int(from_utc.timestamp() * 1000)
        to_ms = int(to_utc.timestamp() * 1000)

        logging.info(f"📅 Trayendo alarmas desde {start_of_day} hasta {now} (ms: {from_ms} → {to_ms})")

        # === Paginación manual ===
        all_alarms = []
        offset = 0
        page_size = 200
        max_alarms = 10_000

        token = get_token()
        headers = {"Authorization": f"Bearer {token}"}

        while len(all_alarms) < max_alarms:
            url = (
                f"https://alarmsone.manageengine.com/rest/json/listAlarms"
                f"?fromDate={from_ms}&toDate={to_ms}&filter=all&size={page_size}&from={offset}"
            )

            with httpx.Client(timeout=30) as client:
                response = client.get(url, headers=headers)
                response.raise_for_status()
                data = response.json()

            alarms = data.get("alarms", [])
            if not alarms:
                break

            all_alarms.extend(alarms)
            offset += len(alarms)

            logging.info(
                f"📦 Página {offset // page_size}, {len(alarms)} alarmas cargadas (total: {len(all_alarms)})"
            )

            # Cortar si se llegó al máximo o ya no hay más datos
            if len(all_alarms) >= max_alarms or len(alarms) < page_size:
                break

        logging.info(f"📊 Total alarmas recibidas hoy: {len(all_alarms)}")

        # === Ingesta a la base de datos ===
        count_inserted = 0
        for item in all_alarms:
            alarm_obj = _map_api_alarm_to_model(item)
            if not alarm_obj:
                continue
            if Alarm.objects.filter(alertid=alarm_obj.alertid).exists():
                continue
            alarm_obj.save()
            count_inserted += 1

        logging.info(f"✅ Ingesta diaria completada. Nuevas filas insertadas: {count_inserted}")

    except Exception as e:
        logging.exception(f"❌ Error inesperado durante la ingesta diaria: {e}")


@shared_task
def ingesta_mensual_ciclica():
    """
    Ingresa datos históricos del último mes dividiendo en tramos de 5 días,
    paginando en bloques de 200 hasta un máximo de 10.000 alarmas por tramo.
    """
    try:
        logging.info("🚀 Inicio de ingesta histórica mensual")

        tz = pytz_timezone("America/Santiago")
        today = datetime.now(tz)

        # Rango de los últimos 30 días
        start_date = today - timedelta(days=30)
        end_date = start_date + timedelta(days=5)

        total_inserted = 0
        tramo_num = 1

        while start_date < today:
            logging.info(f"📆 Tramo {tramo_num}: {start_date} → {end_date}")

            # Convertir a UTC
            from_utc = start_date.astimezone(dt_timezone.utc)
            to_utc = end_date.astimezone(dt_timezone.utc)

            from_ms = int(from_utc.timestamp() * 1000)
            to_ms = int(to_utc.timestamp() * 1000)

            # === Paginación manual ===
            all_alarms = []
            offset = 0
            page_size = 200
            max_alarms = 10_000

            token = get_token()
            headers = {"Authorization": f"Bearer {token}"}

            while len(all_alarms) < max_alarms:
                url = (
                    f"https://alarmsone.manageengine.com/rest/json/listAlarms"
                    f"?fromDate={from_ms}&toDate={to_ms}&filter=all&size={page_size}&from={offset}"
                )

                with httpx.Client(timeout=30) as client:
                    response = client.get(url, headers=headers)
                    response.raise_for_status()
                    data = response.json()

                alarms = data.get("alarms", [])
                if not alarms:
                    break

                all_alarms.extend(alarms)
                offset += len(alarms)

                logging.info(
                    f"📦 Tramo {tramo_num}: página {offset // page_size}, {len(alarms)} alarmas, total {len(all_alarms)}"
                )

                # Cortar si ya se alcanzó el límite API
                if len(all_alarms) >= max_alarms or len(alarms) < page_size:
                    break

            logging.info(
                f"📊 Tramo {tramo_num} completado: {len(all_alarms)} alarmas obtenidas del API."
            )

            # === Ingesta a la base de datos ===
            count_inserted = 0
            for item in all_alarms:
                alarm_obj = _map_api_alarm_to_model(item)
                if not alarm_obj:
                    continue
                if Alarm.objects.filter(alertid=alarm_obj.alertid).exists():
                    continue
                alarm_obj.save()
                count_inserted += 1

            logging.info(f"✅ Tramo {tramo_num}: {count_inserted} nuevas alarmas insertadas.")
            total_inserted += count_inserted

            # Avanzar al siguiente tramo
            start_date = end_date
            end_date = min(end_date + timedelta(days=5), today)
            tramo_num += 1

        logging.info(f"🏁 Ingesta mensual finalizada. Total insertadas: {total_inserted}")

    except Exception as e:
        logging.exception(f"❌ Error inesperado durante la ingesta histórica: {e}")