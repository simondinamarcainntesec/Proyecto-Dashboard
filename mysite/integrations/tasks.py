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
from django.db import connection
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from inyeccion_api.models import Alarm
from inyeccion_api.utils import _map_api_alarm_to_model

# ✅ IMPORTS tenants (incluye contratos y usuarios)
from tenants.models import Tenant, Client, TenantUser, Tenants_contracts

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
    token = os.getenv("SITE24X7_OAUTH_TOKEN")
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

        # =========================
        # TRUNCATE previo
        # =========================
        logger.warning("🧹 Truncando tabla public.inyeccion_api_alarm antes de la ingesta...")
        with connection.cursor() as cursor:
            cursor.execute("TRUNCATE TABLE public.inyeccion_api_alarm;")
        logger.warning("✅ Tabla public.inyeccion_api_alarm truncada.")

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
            return " ".join((s or "").strip().lower().split())

        OMIT_NAME = norm_name("Inntesec SpA")

        for acc in accounts:
            name = acc.get("name") or acc.get("account_name")
            name = clean(name)
            if not name:
                continue

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

        headers = _build_site24x7_headers()
        if not headers:
            return

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

            if getattr(client_obj, "site24x7_user_group", None) != groups_str:
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


# =========================================================
# NUEVA TAREA: Sincronizar contratos (MODIFICADA)
# - Webhook devuelve "account" (nombre empresa)
# - Se resuelve tenant_id desde public.tenants_tenant (id,name)
#   uniendo: tenants_tenant.name == account
# - Se guarda en agent.tenants_contracts
# - + Regla: NO pisar contratos vigentes si contract_id ya existe
# =========================================================

def _contracts_parse_date(value):
    """
    Webhook trae DD-MM-YYYY (ej: 01-11-2025). Soporta variantes comunes.
    """
    from datetime import date as dt_date

    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, dt_date):
        return value

    s = str(value).strip()
    for fmt in ("%d-%m-%Y", "%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"[Contracts] Formato de fecha no soportado: {s!r}")


def _contracts_extract_rows(payload):
    """
    Normaliza JSON a lista de dicts:
    - lista -> lista
    - dict con lista interna -> primera lista interna de dicts
    - dict sin listas -> [dict]
    """
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    if isinstance(payload, dict):
        for v in payload.values():
            if isinstance(v, list) and v and all(isinstance(x, dict) for x in v):
                return v
        return [payload]
    return []


def _contracts_fetch_tenant_map(account_names):
    """
    Mapping exacto {name: id} desde public.tenants_tenant.
    """
    names = [str(n).strip() for n in (account_names or []) if n and str(n).strip()]
    if not names:
        return {}

    sql = """
        SELECT id, name
        FROM public.tenants_tenant
        WHERE name = ANY(%s)
    """
    with connection.cursor() as cur:
        cur.execute(sql, (names,))
        rows = cur.fetchall()

    return {str(name): int(id_) for (id_, name) in rows}


def _contracts_detect_conflict_target():
    """
    Preferencia:
      - (tenant_id, contract_id) si existe UNIQUE/PK con esas columnas
      - fallback (contract_id)
    """
    sql = """
      WITH idx_cols AS (
        SELECT
          array_agg(a.attname ORDER BY x.ord) AS cols
        FROM pg_index i
        JOIN pg_class t ON t.oid = i.indrelid
        JOIN pg_namespace n ON n.oid = t.relnamespace
        JOIN LATERAL unnest(i.indkey) WITH ORDINALITY AS x(attnum, ord) ON TRUE
        JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = x.attnum
        WHERE n.nspname = 'agent'
          AND t.relname = 'tenants_contracts'
          AND (i.indisprimary OR i.indisunique)
        GROUP BY i.indexrelid
      )
      SELECT cols
      FROM idx_cols;
    """
    with connection.cursor() as cur:
        cur.execute(sql)
        idx_list = [r[0] for r in cur.fetchall()]

    for cols in idx_list:
        if cols == ["tenant_id", "contract_id"]:
            return "(tenant_id, contract_id)"
    return "(contract_id)"


def _contracts_bulk_execute(cur, sql_values_style, values, page_size=500):
    """
    Ejecuta INSERT masivo compatible con:
    - psycopg (v3): psycopg.extras.execute_values
    - psycopg2: psycopg2.extras.execute_values
    - fallback: executemany
    """
    # 1) psycopg v3
    try:
        from psycopg.extras import execute_values  # type: ignore
        execute_values(cur, sql_values_style, values, page_size=page_size)
        return
    except Exception:
        pass

    # 2) psycopg2
    try:
        from psycopg2.extras import execute_values  # type: ignore
        execute_values(cur, sql_values_style, values, page_size=page_size)
        return
    except Exception:
        pass

    # 3) Fallback executemany
    sql_one = """
        INSERT INTO agent.tenants_contracts (
            tenant_id,
            contract_id,
            contract_name,
            support_plan,
            support_plan_type,
            start_date,
            expiry_date,
            status,
            account,
            serviceplan_id,
            account_id,
            account_ciid
        )
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """
    if "ON CONFLICT" in sql_values_style:
        tail = sql_values_style.split("ON CONFLICT", 1)[1]
        sql_one += "\nON CONFLICT " + tail.lstrip()

    cur.executemany(sql_one, values)


def _is_expired_by_date(expiry_date, today) -> bool:
    return bool(expiry_date is not None and expiry_date < today)


def _existing_contracts_map(conflict_target: str, ready_rows: list[dict], today):
    """
    Devuelve un mapa con contratos existentes para decisión de "skip upsert".
    Keys:
      - si conflict_target == (tenant_id, contract_id): (tenant_id, contract_id)
      - si conflict_target == (contract_id): contract_id
    Value: dict con status y expiry_date
    """
    if not ready_rows:
        return {}

    if conflict_target == "(tenant_id, contract_id)":
        tenant_ids = sorted({int(x["tenant_id"]) for x in ready_rows if x.get("tenant_id") is not None})
        contract_ids = sorted({str(x["contract_id"]) for x in ready_rows if x.get("contract_id")})
        qs = Tenants_contracts.objects.filter(tenant_id__in=tenant_ids, contract_id__in=contract_ids)
        out = {}
        for r in qs.values("tenant_id", "contract_id", "status", "expiry_date"):
            out[(int(r["tenant_id"]), str(r["contract_id"]))] = {
                "status": (r["status"] or "").strip(),
                "expiry_date": r["expiry_date"],
                "expired_by_date": _is_expired_by_date(r["expiry_date"], today),
            }
        return out

    # fallback: contract_id
    contract_ids = sorted({str(x["contract_id"]) for x in ready_rows if x.get("contract_id")})
    qs = Tenants_contracts.objects.filter(contract_id__in=contract_ids)
    out = {}
    for r in qs.values("contract_id", "status", "expiry_date"):
        out[str(r["contract_id"])] = {
            "status": (r["status"] or "").strip(),
            "expiry_date": r["expiry_date"],
            "expired_by_date": _is_expired_by_date(r["expiry_date"], today),
        }
    return out


def _should_skip_upsert(conflict_target: str, existing_map: dict, row: dict, today) -> bool:
    """
    Regla pedida:
    - Si el contrato ya existe (mismo id / key):
        - Upsert SOLO si (ya expiró) [por fecha o status Expired]
        - Si sigue vigente => IGNORAR (no pisar)
    """
    # Key
    if conflict_target == "(tenant_id, contract_id)":
        key = (int(row["tenant_id"]), str(row["contract_id"]))
    else:
        key = str(row["contract_id"])

    existing = existing_map.get(key)
    if not existing:
        return False  # no existe => insertar/upsert normal

    existing_status = (existing.get("status") or "").strip()
    existing_expired = bool(existing.get("expired_by_date")) or (existing_status == "Expired")

    incoming_expired = _is_expired_by_date(row.get("expiry_date"), today) or ((row.get("status") or "").strip() == "Expired")

    # Si alguno indica expirado => upsert permitido
    if existing_expired or incoming_expired:
        return False

    # Si sigue vigente => ignorar
    # Consideramos vigente: status Active y expiry_date >= hoy o expiry_date NULL
    if existing_status == "Active" and (existing.get("expiry_date") is None or existing.get("expiry_date") >= today):
        return True

    # fallback seguro: si no está claro, no saltar
    return False


@shared_task(bind=True, max_retries=5, default_retry_delay=15)
def sync_tenants_contracts_from_webhook(self):
    """
    Consulta webhook Contratos y hace UPSERT en agent.tenants_contracts
    resolviendo tenant_id por join: public.tenants_tenant.name == account.

    + Regla: si contract_id ya existe y sigue vigente => NO pisar (skip).
            si ya expiró => sí upsert.
    """
    try:
        url = os.getenv("INNTESEC_WEBHOOK_URL") or getattr(settings, "INNTESEC_WEBHOOK_URL", None)
        passkey = os.getenv("INNTESEC_WEBHOOK_PASSKEY") or getattr(settings, "INNTESEC_WEBHOOK_PASSKEY", None)
        params = {"value": "Contratos"}

        if not url or not passkey:
            raise RuntimeError("Faltan INNTESEC_WEBHOOK_URL / INNTESEC_WEBHOOK_PASSKEY (env o settings).")

        headers = {"passkey": passkey}

        with httpx.Client(timeout=30) as client:
            resp = client.get(url, headers=headers, params=params)
            resp.raise_for_status()
            payload = resp.json()

        rows = _contracts_extract_rows(payload)
        if not rows:
            logger.warning("[Contracts] JSON recibido pero sin filas parseables. root=%s", type(payload).__name__)
            return {"received": 0, "upserted": 0, "skipped_no_tenant_match": 0, "skipped_active_existing": 0}

        normalized = []
        accounts = []

        for r in rows:
            contract_id = str(r.get("contract_id", "")).strip()
            if not contract_id:
                continue

            account = (r.get("account") or "").strip()

            item = {
                "tenant_id": None,  # se resuelve
                "contract_id": contract_id,
                "contract_name": (r.get("contract_name") or "").strip(),
                "support_plan": (r.get("support_plan") or "").strip(),
                "support_plan_type": (r.get("support_plan_type") or "").strip(),
                "start_date": _contracts_parse_date(r.get("start_date")),
                "expiry_date": _contracts_parse_date(r.get("expiry_date")),
                "status": (r.get("status") or "").strip(),
                "account": account,
                "serviceplan_id": str(r.get("serviceplan_id", "")).strip(),
                "account_id": str(r.get("account_id", "")).strip(),
                "account_ciid": str(r.get("account_ciid", "")).strip(),
            }
            normalized.append(item)
            if account:
                accounts.append(account)

        if not normalized:
            return {"received": len(rows), "upserted": 0, "skipped_no_tenant_match": 0, "skipped_active_existing": 0}

        # resolve tenant_id
        tenant_map = _contracts_fetch_tenant_map(list(set(accounts)))
        for x in normalized:
            x["tenant_id"] = tenant_map.get(x["account"])

        ready = [x for x in normalized if x["tenant_id"] is not None]
        skipped_no_tenant = len(normalized) - len(ready)

        if not ready:
            logger.warning("[Contracts] Ningún match account->tenant. Ejemplos=%s", list(set(accounts))[:10])
            return {"received": len(rows), "upserted": 0, "skipped_no_tenant_match": skipped_no_tenant, "skipped_active_existing": 0}

        conflict_target = _contracts_detect_conflict_target()

        # ✅ regla nueva: skip si existe y sigue vigente
        today = timezone.localdate()
        existing_map = _existing_contracts_map(conflict_target, ready, today)

        to_upsert = []
        skipped_active_existing = 0

        for x in ready:
            if _should_skip_upsert(conflict_target, existing_map, x, today):
                skipped_active_existing += 1
                continue
            to_upsert.append(x)

        if not to_upsert:
            logger.info(
                "[Contracts] Sync: todo fue skip (vigentes). received=%s matched=%s skipped_active_existing=%s skipped_no_tenant=%s",
                len(rows),
                len(ready),
                skipped_active_existing,
                skipped_no_tenant,
            )

            # Aun así enforce por si hay expiraciones por fecha ya existentes
            affected_tenant_ids = sorted({int(x["tenant_id"]) for x in ready if x.get("tenant_id") is not None})
            if affected_tenant_ids:
                contracts_enforce_expiry_and_sync_tenants.delay(only_tenant_ids=affected_tenant_ids)

            return {
                "received": len(rows),
                "upserted": 0,
                "skipped_no_tenant_match": skipped_no_tenant,
                "skipped_active_existing": skipped_active_existing,
                "conflict_target": conflict_target,
            }

        sql_values_style = f"""
            INSERT INTO agent.tenants_contracts (
                tenant_id,
                contract_id,
                contract_name,
                support_plan,
                support_plan_type,
                start_date,
                expiry_date,
                status,
                account,
                serviceplan_id,
                account_id,
                account_ciid
            )
            VALUES %s
            ON CONFLICT {conflict_target} DO UPDATE SET
                tenant_id         = EXCLUDED.tenant_id,
                contract_name     = EXCLUDED.contract_name,
                support_plan      = EXCLUDED.support_plan,
                support_plan_type = EXCLUDED.support_plan_type,
                start_date        = EXCLUDED.start_date,
                expiry_date       = EXCLUDED.expiry_date,
                status            = EXCLUDED.status,
                account           = EXCLUDED.account,
                serviceplan_id    = EXCLUDED.serviceplan_id,
                account_id        = EXCLUDED.account_id,
                account_ciid      = EXCLUDED.account_ciid
        """

        values = [
            (
                x["tenant_id"],
                x["contract_id"],
                x["contract_name"],
                x["support_plan"],
                x["support_plan_type"],
                x["start_date"],
                x["expiry_date"],
                x["status"],
                x["account"],
                x["serviceplan_id"],
                x["account_id"],
                x["account_ciid"],
            )
            for x in to_upsert
        ]

        with transaction.atomic(), connection.cursor() as cur:
            _contracts_bulk_execute(cur, sql_values_style, values, page_size=500)

        # ✅ LOG
        logger.info(
            "[Contracts] Sync OK received=%s matched=%s upserted=%s skipped_active_existing=%s skipped_no_tenant_match=%s conflict=%s",
            len(rows),
            len(ready),
            len(values),
            skipped_active_existing,
            skipped_no_tenant,
            conflict_target,
        )

        # ✅ Enforce inmediato SOLO para tenants afectados (incluye los que se skipearon)
        affected_tenant_ids = sorted({int(x["tenant_id"]) for x in ready if x.get("tenant_id") is not None})
        if affected_tenant_ids:
            contracts_enforce_expiry_and_sync_tenants.delay(only_tenant_ids=affected_tenant_ids)

        return {
            "received": len(rows),
            "matched": len(ready),
            "upserted": len(values),
            "skipped_no_tenant_match": skipped_no_tenant,
            "skipped_active_existing": skipped_active_existing,
            "conflict_target": conflict_target,
            "affected_tenant_ids": affected_tenant_ids,
        }

    except Exception as e:
        logger.exception("❌ [Contracts] Error en sync_tenants_contracts_from_webhook: %s", e)
        raise self.retry(exc=e)


# ==============================
# CONTRACTS -> TENANT ACTIVATION
# ==============================
MANDATORY_CONTRACT_NAMES = {"POC Inntesec Agent", "Inntesec Agent"}
STATUS_ACTIVE = "Active"
STATUS_EXPIRED = "Expired"


def _sync_tenant_and_users(tenant: Tenant, active: bool) -> int:
    """
    Activa/desactiva tenant + usuarios (excepto superusers).
    Retorna cantidad de usuarios actualizados.
    """
    if tenant.is_active != active:
        tenant.is_active = active
        tenant.save(update_fields=["is_active"])

    updated = (
        TenantUser.objects
        .filter(tenant=tenant)
        .exclude(is_superuser=True)
        .update(is_active=active)
    )
    return int(updated or 0)


@shared_task(bind=True, max_retries=3, default_retry_delay=10)
def contracts_enforce_expiry_and_sync_tenants(self, only_tenant_ids: list[int] | None = None):
    """
    ✅ REGLA FINAL (solo en Celery):
    - Si el tenant tiene AL MENOS 1 contrato mandatorio vigente => NO TOCAR usuarios (ni tenant).
    - Si NO tiene contratos mandatorios vigentes => desactivar tenant + desactivar usuarios activos.

    Vigente = status=Active y (expiry_date >= hoy OR expiry_date IS NULL)

    Además:
    - Si expiry_date < hoy => status=Expired (solo contratos mandatorios)

    ✅ LOGS: contratos expirados + tenants desactivados + usuarios desactivados + tenants omitidos por estar vigentes.
    """
    try:
        today = timezone.localdate()

        base_qs = Tenants_contracts.objects.filter(
            contract_name__in=list(MANDATORY_CONTRACT_NAMES),
        )
        if only_tenant_ids:
            base_qs = base_qs.filter(tenant_id__in=only_tenant_ids)

        # 1) Marcar Expired por fecha (solo mandatorios)
        expired_by_date_qs = base_qs.filter(
            expiry_date__isnull=False,
            expiry_date__lt=today,
        ).exclude(status=STATUS_EXPIRED)

        n_contracts_marked_expired = int(expired_by_date_qs.update(status=STATUS_EXPIRED) or 0)

        # 2) Tenants a revisar
        tenant_ids = list(base_qs.values_list("tenant_id", flat=True).distinct())
        if not tenant_ids:
            logger.info("[ContractsEnforce] today=%s no tenants to process.", today)
            return {
                "today": str(today),
                "tenants_processed": 0,
                "contracts_marked_expired": n_contracts_marked_expired,
                "tenants_deactivated": 0,
                "tenants_skipped_active": 0,
                "users_disabled_total": 0,
                "details": [],
            }

        details = []
        users_disabled_total = 0
        tenants_deactivated = 0
        tenants_skipped_active = 0

        with transaction.atomic():
            tenants = Tenant.objects.select_for_update().filter(id__in=tenant_ids)
            tenant_map = {t.id: t for t in tenants}

            for tid in tenant_ids:
                tenant = tenant_map.get(tid)
                if not tenant:
                    logger.warning("[ContractsEnforce] tenant_id=%s no existe en tenants_tenant. Se omite.", tid)
                    continue

                # ¿Tiene al menos 1 contrato vigente?
                any_active_vigente = base_qs.filter(
                    tenant_id=tid,
                    status=STATUS_ACTIVE,
                ).filter(
                    Q(expiry_date__isnull=True) | Q(expiry_date__gte=today)
                ).exists()

                # ✅ Si está vigente -> NO TOCAR NADA
                if any_active_vigente:
                    tenants_skipped_active += 1
                    details.append({
                        "tenant_id": tid,
                        "tenant_name": tenant.name,
                        "has_active_contract": True,
                        "action": "skip_no_changes",
                        "tenant_was_active": bool(getattr(tenant, "is_active", True)),
                        "users_disabled": 0,
                    })
                    continue

                # ❌ Si NO hay contrato vigente -> desactivar tenant + desactivar usuarios activos
                tenant_was_active = bool(getattr(tenant, "is_active", True))
                if tenant_was_active:
                    tenant.is_active = False
                    tenant.save(update_fields=["is_active"])
                    tenants_deactivated += 1

                # Desactivar SOLO los usuarios actualmente activos (no pisa inactivos manuales)
                qs_users = (
                    TenantUser.objects
                    .filter(tenant=tenant)
                    .exclude(is_superuser=True)
                    .filter(is_active=True)
                )
                u_disabled = int(qs_users.update(is_active=False) or 0)
                users_disabled_total += u_disabled

                details.append({
                    "tenant_id": tid,
                    "tenant_name": tenant.name,
                    "has_active_contract": False,
                    "action": "deactivated_tenant_and_users",
                    "tenant_was_active": tenant_was_active,
                    "users_disabled": u_disabled,
                })

        logger.info(
            "[ContractsEnforce] today=%s tenants_processed=%s contracts_marked_expired=%s tenants_deactivated=%s tenants_skipped_active=%s users_disabled_total=%s",
            today,
            len(details),
            n_contracts_marked_expired,
            tenants_deactivated,
            tenants_skipped_active,
            users_disabled_total,
        )

        # logs por tenant (útil para debug)
        for d in details:
            logger.info(
                "[ContractsEnforce][Tenant] id=%s name=%s action=%s has_active_contract=%s tenant_was_active=%s users_disabled=%s",
                d["tenant_id"],
                d["tenant_name"],
                d["action"],
                d["has_active_contract"],
                d["tenant_was_active"],
                d["users_disabled"],
            )

        return {
            "today": str(today),
            "tenants_processed": len(details),
            "contracts_marked_expired": n_contracts_marked_expired,
            "tenants_deactivated": tenants_deactivated,
            "tenants_skipped_active": tenants_skipped_active,
            "users_disabled_total": users_disabled_total,
            "details": details,
        }

    except Exception as e:
        logger.exception("❌ [ContractsEnforce] Error: %s", e)
        raise self.retry(exc=e)

