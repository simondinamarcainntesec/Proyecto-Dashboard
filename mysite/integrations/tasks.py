from __future__ import annotations

from datetime import datetime, timedelta, timezone as dt_timezone
from pytz import timezone as pytz_timezone

import json
import logging
import os
import subprocess
from pathlib import Path

import httpx
from celery import shared_task
from django.conf import settings

from inyeccion_api.models import Alarm
from inyeccion_api.utils import _map_api_alarm_to_model
from tenants.models import Tenant, Client  # añadimos Client

TOKEN_FILE = Path(settings.BASE_DIR) / "token.txt"

logger = logging.getLogger(__name__)

# Zoho ServiceDesk / Soporte Inntesec
SOPORTE_BASE_URL = "https://soporte.inntesec.com/api/v3"
SOPORTE_USERS_URL = f"{SOPORTE_BASE_URL}/users"

# Site24x7
SITE24X7_BASE_URL = "https://www.site24x7.com/api"


# =========================================================
# TOKEN: mismo patrón que realtime (ejecutar obtener_token.py)
# - Este flujo necesita EL PRIMER TOKEN (index 0)
# - Si stdout trae "TOKEN1  TOKEN2", se separa por whitespace
# =========================================================
def _get_token_via_script_local(token_index: int = 0) -> str:
    """
    Ejecuta /home/inntesec-ia/Proyecto-Dashboard/obtener_token.py y extrae un token.

    - Si stdout trae múltiples tokens (separados por espacios / nuevas líneas),
      toma el token en la posición `token_index` (por defecto el primero).
    """
    script_path = "/home/inntesec-ia/Proyecto-Dashboard/obtener_token.py"

    try:
        out = subprocess.run(
            ["python3", script_path],
            capture_output=True,
            text=True,
            timeout=25,
        )
    except Exception as e:
        logger.exception("[TOKEN] Error ejecutando obtener_token.py: %s", e)
        raise RuntimeError(f"Error ejecutando obtener_token.py: {e}") from e

    if out.returncode != 0:
        logger.error(
            "[TOKEN] obtener_token.py falló exit=%s stderr=%s",
            out.returncode,
            (out.stderr or out.stdout),
        )
        raise RuntimeError(
            f"obtener_token.py exit={out.returncode} stderr={out.stderr or out.stdout}"
        )

    stdout_raw = (out.stdout or "").strip()
    if not stdout_raw:
        logger.error(
            "[TOKEN] obtener_token.py devolvió stdout vacío. stderr=%s",
            out.stderr,
        )
        raise RuntimeError("obtener_token.py devolvió vacío")

    parts = stdout_raw.split()  # colapsa múltiples espacios / saltos
    if not parts:
        raise RuntimeError("No se pudo parsear stdout de obtener_token.py")

    # Si piden un índice que no existe, fallback al primero
    idx = token_index if 0 <= token_index < len(parts) else 0
    token = (parts[idx] or "").strip()

    if not token:
        logger.error(
            "[TOKEN] Token vacío tras parseo. stdout_raw=%r stderr=%s",
            stdout_raw[:300],
            out.stderr,
        )
        raise RuntimeError("No se pudo extraer token desde obtener_token.py")

    return token


def _persist_token(token: str) -> None:
    try:
        TOKEN_FILE.write_text(token, encoding="utf-8")
    except Exception as e:
        logger.warning("[TOKEN] No se pudo escribir token.txt: %s", e)


def _read_token_file() -> str | None:
    try:
        if TOKEN_FILE.exists():
            t = TOKEN_FILE.read_text(encoding="utf-8").strip()
            return t or None
    except Exception as e:
        logger.warning("[TOKEN] No se pudo leer token.txt: %s", e)
    return None


def _get_alarmsone_token_first() -> str:
    """
    Este flujo (ingesta de AlarmsOne) requiere el PRIMER token.
    Si falla el script, intenta fallback a token.txt.
    """
    try:
        token = _get_token_via_script_local(token_index=0)
        _persist_token(token)
        return token
    except Exception as e:
        logger.error("[TOKEN] Falla obteniendo token por script: %s", e)
        cached = _read_token_file()
        if cached:
            logger.warning("[TOKEN] Usando token cacheado desde token.txt")
            return cached
        raise RuntimeError("No se pudo obtener el token desde obtener_token.py") from e


# === Helper: obtener una página de usuarios desde soporte.inntesec.com ===
def fetch_soporte_users_page(start_index: int = 1, row_count: int = 100) -> dict:
    """
    Llama a https://soporte.inntesec.com/api/v3/users usando input_data en querystring.

    Requiere en settings.py:
        SOPORTE_AUTHTOKEN = "token_zoho"
    """
    authtoken = os.getenv("SOPORTE_AUTHTOKEN")
    if not authtoken:
        logger.error("[SoporteUsers] Falta settings.SOPORTE_AUTHTOKEN")
        raise RuntimeError("Falta SOPORTE_AUTHTOKEN en settings")

    headers = {"authtoken": authtoken}

    payload = {
        "list_info": {
            "sort_field": "name",
            "sort_order": "asc",
            "start_index": start_index,
            "row_count": row_count,
        }
    }

    params = {"input_data": json.dumps(payload)}

    with httpx.Client(timeout=30) as client:
        resp = client.get(SOPORTE_USERS_URL, headers=headers, params=params)
        resp.raise_for_status()
        data = resp.json()

    li = (data or {}).get("list_info", {}) or {}
    logger.info(
        "[SoporteUsers] OK start_index_req=%s row_count_req=%s start_index_resp=%s row_count_resp=%s has_more=%s",
        start_index,
        row_count,
        li.get("start_index"),
        li.get("row_count"),
        li.get("has_more_rows"),
    )
    return data


# === Helper: headers Site24x7 ===
def _build_site24x7_headers():
    """
    Construye los headers para llamar a la API de Site24x7.

    Ideal: usar env SITE24X7_OAUTH_TOKEN
    """
    token = "1000.a6250986ef34e1b792958f60288f9b49.d9334f2f2eee3c3814723b4f08e2f0be"
    if not token:
        logger.error("❌ [Site24x7] Falta SITE24X7_OAUTH_TOKEN en variables de entorno.")
        return None

    return {
        "Accept": "application/json; version=2.0",
        "Authorization": f"Zoho-oauthtoken {token}",
    }


# === Tarea 1: Obtener Token (PRIMER TOKEN) ===
@shared_task(bind=True, max_retries=3, default_retry_delay=10)
def tarea_obtener_token(self):
    """
    Obtiene el token (primer token del stdout) y lo guarda en token.txt.
    """
    try:
        logger.info("🔑 Solicitando token (primer token) ejecutando obtener_token.py ...")
        token = _get_alarmsone_token_first()
        logger.info("✅ Token guardado correctamente en token.txt.")
        return token
    except Exception as e:
        logger.error("❌ Error al obtener token: %s", e)
        raise self.retry(exc=e)


# === Tarea 2: Ingesta API diaria ===
@shared_task
def tarea_ingesta_api():
    """
    Ingresa las alarmas del día actual (desde 00:00 hasta ahora),
    paginando en bloques de 200 hasta un máximo de 10.000 alarmas.
    """
    try:
        logger.info("🚀 Inicio de ingesta diaria de API")

        tz = pytz_timezone("America/Santiago")
        now = datetime.now(tz)

        # Eliminar alarmas con más de 60 días
        limite = now - timedelta(days=60)
        eliminadas, _ = Alarm.objects.filter(event_time__lt=limite).delete()
        logger.info("🧹 Alarmas antiguas eliminadas: %s", eliminadas)

        # Calcular rango de hoy (00:00 → ahora)
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)

        # Convertir a UTC (API usa UTC)
        from_utc = start_of_day.astimezone(dt_timezone.utc)
        to_utc = now.astimezone(dt_timezone.utc)
        from_ms = int(from_utc.timestamp() * 1000)
        to_ms = int(to_utc.timestamp() * 1000)

        logger.info(
            "📅 Trayendo alarmas desde %s hasta %s (ms: %s → %s)",
            start_of_day,
            now,
            from_ms,
            to_ms,
        )

        # === Paginación manual ===
        all_alarms = []
        offset = 0
        page_size = 200
        max_alarms = 10_000

        # PRIMER TOKEN (como realtime) + header correcto
        token = _get_alarmsone_token_first()
        headers = {"Authorization": f"Zoho-oauthtoken {token}"}

        while len(all_alarms) < max_alarms:
            url = (
                "https://alarmsone.manageengine.com/rest/json/listAlarms"
                f"?fromDate={from_ms}&toDate={to_ms}&filter=all&size={page_size}&from={offset}"
            )

            with httpx.Client(timeout=30) as client:
                response = client.get(url, headers=headers)
                response.raise_for_status()
                data = response.json()

            alarms = data.get("alarms", []) or data.get("data", []) or []
            if not alarms:
                break

            all_alarms.extend(alarms)
            offset += len(alarms)

            logger.info(
                "📦 Página %s, %s alarmas cargadas (total: %s)",
                max(1, offset // page_size),
                len(alarms),
                len(all_alarms),
            )

            if len(all_alarms) >= max_alarms or len(alarms) < page_size:
                break

        logger.info("📊 Total alarmas recibidas hoy: %s", len(all_alarms))

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

        logger.info("✅ Ingesta diaria completada. Nuevas filas insertadas: %s", count_inserted)

    except Exception as e:
        logger.exception("❌ Error inesperado durante la ingesta diaria: %s", e)


@shared_task
def ingesta_mensual_ciclica():
    """
    Ingresa datos históricos del último mes dividiendo en tramos de 5 días,
    paginando en bloques de 200 hasta un máximo de 10.000 alarmas por tramo.
    """
    try:
        logger.info("🚀 Inicio de ingesta histórica mensual")

        tz = pytz_timezone("America/Santiago")
        today = datetime.now(tz)

        start_date = today - timedelta(days=30)
        end_date = start_date + timedelta(days=5)

        total_inserted = 0
        tramo_num = 1

        # Token una vez por corrida (primer token)
        token = _get_alarmsone_token_first()
        headers = {"Authorization": f"Zoho-oauthtoken {token}"}

        while start_date < today:
            logger.info("📆 Tramo %s: %s → %s", tramo_num, start_date, end_date)

            from_utc = start_date.astimezone(dt_timezone.utc)
            to_utc = end_date.astimezone(dt_timezone.utc)

            from_ms = int(from_utc.timestamp() * 1000)
            to_ms = int(to_utc.timestamp() * 1000)

            all_alarms = []
            offset = 0
            page_size = 200
            max_alarms = 10_000

            while len(all_alarms) < max_alarms:
                url = (
                    "https://alarmsone.manageengine.com/rest/json/listAlarms"
                    f"?fromDate={from_ms}&toDate={to_ms}&filter=all&size={page_size}&from={offset}"
                )

                with httpx.Client(timeout=30) as client:
                    response = client.get(url, headers=headers)
                    response.raise_for_status()
                    data = response.json()

                alarms = data.get("alarms", []) or data.get("data", []) or []
                if not alarms:
                    break

                all_alarms.extend(alarms)
                offset += len(alarms)

                logger.info(
                    "📦 Tramo %s: página %s, %s alarmas, total %s",
                    tramo_num,
                    max(1, offset // page_size),
                    len(alarms),
                    len(all_alarms),
                )

                if len(all_alarms) >= max_alarms or len(alarms) < page_size:
                    break

            logger.info("📊 Tramo %s completado: %s alarmas obtenidas del API.", tramo_num, len(all_alarms))

            count_inserted = 0
            for item in all_alarms:
                alarm_obj = _map_api_alarm_to_model(item)
                if not alarm_obj:
                    continue
                if Alarm.objects.filter(alertid=alarm_obj.alertid).exists():
                    continue
                alarm_obj.save()
                count_inserted += 1

            logger.info("✅ Tramo %s: %s nuevas alarmas insertadas.", tramo_num, count_inserted)
            total_inserted += count_inserted

            start_date = end_date
            end_date = min(end_date + timedelta(days=5), today)
            tramo_num += 1

        logger.info("🏁 Ingesta mensual finalizada. Total insertadas: %s", total_inserted)

    except Exception as e:
        logger.exception("❌ Error inesperado durante la ingesta histórica: %s", e)


# === NUEVA TAREA: Sincronizar usuarios (clientes) con empresa → tabla Client ===
@shared_task
def tarea_sync_clientes_soporte():
    """
    Recorre las páginas de /users en soporte.inntesec.com y sincroniza
    SOLO los usuarios con empresa (campo 'account' distinto de None)
    hacia la tabla Client, vinculados a Tenant por account['name'].
    """
    try:
        logger.info("👥 Inicio tarea_sync_clientes_soporte (usuarios con empresa)")

        start_index = 1
        row_count_req = 100
        max_loops = 50

        total_raw = 0
        created = 0
        updated = 0
        skipped_no_account = 0
        skipped_no_tenant = 0
        skipped_no_email = 0
        skipped_bad_id = 0

        seen_ids = set()

        for _ in range(max_loops):
            logger.info("[SoporteSyncClientes] Pidiendo página start_index=%s", start_index)
            data = fetch_soporte_users_page(start_index=start_index, row_count=row_count_req)

            users = (data or {}).get("users", []) or []
            list_info = (data or {}).get("list_info", {}) or {}

            if not users:
                logger.info("[SoporteSyncClientes] Página sin usuarios, fin.")
                break

            total_raw += len(users)

            for u in users:
                uid = u.get("id")
                if not uid or uid in seen_ids:
                    continue
                seen_ids.add(uid)

                account = u.get("account")
                if account is None:
                    skipped_no_account += 1
                    continue

                account_name = account.get("name")
                if not account_name:
                    skipped_no_tenant += 1
                    continue

                tenant = Tenant.objects.filter(name__iexact=account_name).first()
                if not tenant:
                    logger.warning(
                        "[SoporteSyncClientes] No Tenant para empresa '%s' (user_id=%s)",
                        account_name,
                        uid,
                    )
                    skipped_no_tenant += 1
                    continue

                email = u.get("email_id")
                if not email:
                    skipped_no_email += 1
                    continue

                name = u.get("name") or ""
                phone = u.get("mobile") or u.get("phone")

                try:
                    client_id = int(uid)
                except (TypeError, ValueError):
                    logger.warning("[SoporteSyncClientes] id no numérico, se omite: %r", uid)
                    skipped_bad_id += 1
                    continue

                _, created_flag = Client.objects.update_or_create(
                    id=client_id,
                    defaults={"tenant": tenant, "name": name, "email": email, "phone": phone},
                )

                if created_flag:
                    created += 1
                else:
                    updated += 1

            has_more = list_info.get("has_more_rows", False)
            resp_start = list_info.get("start_index") or start_index
            resp_count = list_info.get("row_count") or len(users)

            logger.info(
                "[SoporteSyncClientes] Página procesada: resp_start=%s resp_count=%s has_more=%s",
                resp_start,
                resp_count,
                has_more,
            )

            if not has_more or resp_count <= 0:
                break

            start_index = resp_start + resp_count

        summary = {
            "total_raw": total_raw,
            "total_unique_ids": len(seen_ids),
            "created": created,
            "updated": updated,
            "skipped_no_account": skipped_no_account,
            "skipped_no_tenant": skipped_no_tenant,
            "skipped_no_email": skipped_no_email,
            "skipped_bad_id": skipped_bad_id,
        }

        logger.info("👥 tarea_sync_clientes_soporte resumen: %s", summary)
        return summary

    except Exception as e:
        logger.exception("❌ Error en tarea_sync_clientes_soporte: %s", e)
        return {"error": str(e)}


# === NUEVA TAREA: Sincronizar empresas desde soporte.inntesec.com ===
@shared_task
def tarea_sync_empresas():
    """
    Llama a la API de cuentas de soporte.inntesec.com y sincroniza el listado
    de empresas con la tabla tenants_tenant, omitiendo "Inntesec SpA".
    """
    try:
        logger.info("🏢 Inicio sync empresas desde soporte.inntesec.com")

        api_token = os.getenv("API_KEY")
        if not api_token:
            logger.error("❌ No se encontró API_KEY en las variables de entorno.")
            return

        url = "https://soporte.inntesec.com/api/v3/accounts"
        headers = {"authtoken": api_token}

        input_data = {
            "list_info": {"sort_field": "name", "sort_order": "asc", "start_index": 1, "row_count": 100}
        }
        params = {"input_data": json.dumps(input_data)}

        with httpx.Client(timeout=30) as client:
            response = client.get(url, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()

        accounts = data.get("accounts") or data.get("data") or []
        logger.info("🏢 Sync empresas: recibidas %s cuentas desde la API.", len(accounts))

        if accounts:
            logger.info("Ejemplo de cuenta API: %s", json.dumps(accounts[0], ensure_ascii=False)[:1000])

        insertados = 0
        actualizados = 0
        omitidos = 0

        def clean(val):
            if val is None:
                return None
            s = str(val).strip()
            return s or None

        def norm_name(s: str) -> str:
            # normaliza para comparar de forma tolerante (espacios y case)
            return " ".join((s or "").strip().lower().split())

        OMIT_NAME = norm_name("Inntesec SpA")

        for acc in accounts:
            name = acc.get("name") or acc.get("account_name")
            name = clean(name)
            if not name:
                continue

            # === OMITIR Inntesec SpA ===
            if norm_name(name) == OMIT_NAME:
                omitidos += 1
                logger.info("⏭️ Omitiendo empresa (no se guarda): %s", name)
                continue

            udf_fields = acc.get("accountudf_fields") or {}

            alarms_one_id = clean(udf_fields.get("udf_sline_601"))
            site24x7_id = clean(udf_fields.get("udf_sline_602"))
            logs360siem_id = clean(udf_fields.get("udf_sline_603"))

            tenant, created = Tenant.objects.get_or_create(name=name)
            changed = False

            if alarms_one_id is not None and tenant.alarms_one_id != alarms_one_id:
                tenant.alarms_one_id = alarms_one_id
                changed = True

            if logs360siem_id is not None and tenant.logs360siem_id != logs360siem_id:
                tenant.logs360siem_id = logs360siem_id
                changed = True

            if site24x7_id is not None and tenant.site24x7_id != site24x7_id:
                tenant.site24x7_id = site24x7_id
                changed = True

            if changed:
                tenant.save()
                if created:
                    insertados += 1
                else:
                    actualizados += 1
            else:
                if created:
                    insertados += 1

        logger.info(
            "🏢 Sync empresas completado. Recibidas: %s, omitidas: %s, nuevas: %s, actualizadas: %s",
            len(accounts),
            omitidos,
            insertados,
            actualizados,
        )

    except Exception as e:
        logger.exception("❌ Error en tarea_sync_empresas: %s", e)

# === NUEVA TAREA: Sync user_groups Site24x7 → Client.site24x7_user_group (por email) ===
@shared_task
def tarea_sync_site24x7_user_groups():
    """
    Llama a /api/users de Site24x7 y guarda user_groups en Client.site24x7_user_group.
    """
    try:
        logger.info("👤 [Site24x7] Llamando a https://www.site24x7.com/api/users ...")

        token = os.getenv("SITE24X7_OAUTH_TOKEN")
        if not token:
            logger.error("❌ [Site24x7] Falta SITE24X7_OAUTH_TOKEN en variables de entorno.")
            return

        headers = {"Accept": "application/json; version=2.0", "Authorization": f"Zoho-oauthtoken {token}"}

        with httpx.Client(timeout=30) as client:
            resp = client.get("https://www.site24x7.com/api/users", headers=headers)
            resp.raise_for_status()
            data = resp.json()

        users = (data or {}).get("data", []) or []
        logger.info("👤 [Site24x7] Recibidos %s usuarios desde la API.", len(users))

        actualizados = 0
        sin_cliente = 0
        sin_email = 0

        for u in users:
            email = u.get("email_address")
            if not email:
                sin_email += 1
                continue

            user_groups = u.get("user_groups") or []
            groups_str = ",".join(str(g) for g in user_groups) if user_groups else None

            client_obj = Client.objects.filter(email__iexact=email).first()
            if not client_obj:
                sin_cliente += 1
                logger.info(
                    "👤 [Site24x7] No se encontró Client con email=%s para user_id=%s",
                    email,
                    u.get("user_id"),
                )
                continue

            if client_obj.site24x7_user_group != groups_str:
                client_obj.site24x7_user_group = groups_str
                client_obj.save(update_fields=["site24x7_user_group"])
                actualizados += 1

        logger.info(
            "👤 [Site24x7] tarea_sync_site24x7_user_groups completada. Clientes actualizados=%s, sin_cliente=%s, sin_email=%s",
            actualizados,
            sin_cliente,
            sin_email,
        )

    except Exception as e:
        logger.exception("❌ [Site24x7] Error en tarea_sync_site24x7_user_groups: %s", e)
        return
