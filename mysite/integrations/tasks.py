from datetime import datetime, timedelta, timezone as dt_timezone
from pytz import timezone as pytz_timezone
import logging, os, httpx, json
from celery import shared_task
from django.conf import settings
from pathlib import Path

from inyeccion_api.models import Alarm
from integrations.alarmsone import obtener_token_via_script, get_token
from inyeccion_api.utils import _map_api_alarm_to_model
from tenants.models import Tenant, Client  # 👈 añadimos Client

TOKEN_FILE = Path(settings.BASE_DIR) / "token.txt"

# Zoho ServiceDesk / Soporte Inntesec
SOPORTE_BASE_URL = "https://soporte.inntesec.com/api/v3"
SOPORTE_USERS_URL = f"{SOPORTE_BASE_URL}/users"

# Site24x7
SITE24X7_BASE_URL = "https://www.site24x7.com/api"


# === Helper: obtener una página de usuarios desde soporte.inntesec.com ===
def fetch_soporte_users_page(start_index: int = 1, row_count: int = 100) -> dict:
    """
    Llama a https://soporte.inntesec.com/api/v3/users usando input_data en querystring.

    Requiere en settings.py:
        SOPORTE_AUTHTOKEN = "token_zoho"
    """
    authtoken = getattr(settings, "SOPORTE_AUTHTOKEN", None)
    if not authtoken:
        logging.error("[SoporteUsers] Falta settings.SOPORTE_AUTHTOKEN")
        raise RuntimeError("Falta SOPORTE_AUTHTOKEN en settings")

    headers = {
        "authtoken": authtoken,
    }

    payload = {
        "list_info": {
            "sort_field": "name",
            "sort_order": "asc",
            "start_index": start_index,
            "row_count": row_count,
        }
    }

    params = {
        "input_data": json.dumps(payload)
    }

    with httpx.Client(timeout=30) as client:
        resp = client.get(SOPORTE_USERS_URL, headers=headers, params=params)
        resp.raise_for_status()
        data = resp.json()

    li = (data or {}).get("list_info", {}) or {}
    logging.info(
        "[SoporteUsers] OK start_index_req=%s row_count_req=%s "
        "start_index_resp=%s row_count_resp=%s has_more=%s",
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

    Requiere en variables de entorno:
        SITE24X7_OAUTH_TOKEN="xxxxx"
    """
    token = "1000.a6250986ef34e1b792958f60288f9b49.d9334f2f2eee3c3814723b4f08e2f0be"
    if not token:
        logging.error("❌ [Site24x7] Falta SITE24X7_OAUTH_TOKEN en variables de entorno.")
        return None

    return {
        "Accept": "application/json; version=2.0",
        "Authorization": f"Zoho-oauthtoken {token}",
    }


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


# === Tarea 2: Ingesta API diaria ===
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

        # Eliminar alarmas con más de 60 días
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
                "https://alarmsone.manageengine.com/rest/json/listAlarms"
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
                    "https://alarmsone.manageengine.com/rest/json/listAlarms"
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


# === NUEVA TAREA: Sincronizar usuarios (clientes) con empresa → tabla Client ===
@shared_task
def tarea_sync_clientes_soporte():
    """
    Recorre las páginas de /users en soporte.inntesec.com y sincroniza
    SOLO los usuarios con empresa (campo 'account' distinto de None)
    hacia la tabla Client, vinculados a Tenant por account['name'].
    """
    try:
        logging.info("👥 Inicio tarea_sync_clientes_soporte (usuarios con empresa)")

        start_index = 1
        row_count_req = 100
        max_loops = 50  # seguridad anti-bucle

        total_raw = 0
        created = 0
        updated = 0
        skipped_no_account = 0
        skipped_no_tenant = 0
        skipped_no_email = 0
        skipped_bad_id = 0

        seen_ids = set()  # evitar duplicar usuarios por id

        for loop in range(max_loops):
            logging.info("[SoporteSyncClientes] Pidiendo página start_index=%s", start_index)
            data = fetch_soporte_users_page(
                start_index=start_index,
                row_count=row_count_req,
            )

            users = (data or {}).get("users", []) or []
            list_info = (data or {}).get("list_info", {}) or {}

            if not users:
                logging.info("[SoporteSyncClientes] Página sin usuarios, fin.")
                break

            total_raw += len(users)

            for u in users:
                uid = u.get("id")
                if not uid:
                    continue

                # Evitar repetir usuarios si la API devuelve solapados
                if uid in seen_ids:
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
                    logging.warning(
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
                    logging.warning(
                        "[SoporteSyncClientes] id no numérico, se omite: %r", uid
                    )
                    skipped_bad_id += 1
                    continue

                obj, created_flag = Client.objects.update_or_create(
                    id=client_id,
                    defaults={
                        "tenant": tenant,
                        "name": name,
                        "email": email,
                        "phone": phone,
                    },
                )

                if created_flag:
                    created += 1
                else:
                    updated += 1

            has_more = list_info.get("has_more_rows", False)
            resp_start = list_info.get("start_index") or start_index
            resp_count = list_info.get("row_count") or len(users)

            logging.info(
                "[SoporteSyncClientes] Página procesada: resp_start=%s resp_count=%s has_more=%s",
                resp_start,
                resp_count,
                has_more,
            )

            if not has_more:
                logging.info("[SoporteSyncClientes] has_more_rows=False, fin de paginación.")
                break

            if resp_count <= 0:
                logging.warning(
                    "[SoporteSyncClientes] resp_count <= 0, se detiene para evitar bucle."
                )
                break

            # Siguiente bloque
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

        logging.info("👥 tarea_sync_clientes_soporte resumen: %s", summary)
        return summary

    except Exception as e:
        logging.exception(f"❌ Error en tarea_sync_clientes_soporte: {e}")
        return {"error": str(e)}


# === NUEVA TAREA: Sincronizar empresas desde soporte.inntesec.com ===
@shared_task
def tarea_sync_empresas():
    """
    Llama a la API de cuentas de soporte.inntesec.com y sincroniza el listado
    de empresas con la tabla tenants_tenant.

    - Crea el Tenant si no existe (por name).
    - Si ya existe, SOLO actualiza alarms_one_id / logs360siem_id / site24x7_id
      cuando la API trae un valor NO vacío (para no pisar datos existentes).
    """
    try:
        logging.info("🏢 Inicio sync empresas desde soporte.inntesec.com")

        # 1) Obtener token desde variable de entorno
        api_token = os.getenv("API_KEY")
        if not api_token:
            logging.error("❌ No se encontró API_KEY en las variables de entorno.")
            return

        url = "https://soporte.inntesec.com/api/v3/accounts"

        headers = {
            "authtoken": api_token,
        }

        input_data = {
            "list_info": {
                "sort_field": "name",
                "sort_order": "asc",
                "start_index": 1,
                "row_count": 100,
            }
        }

        params = {
            "input_data": json.dumps(input_data)
        }

        with httpx.Client(timeout=30) as client:
            response = client.get(url, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()

        accounts = data.get("accounts") or data.get("data") or []
        logging.info(f"🏢 Sync empresas: recibidas {len(accounts)} cuentas desde la API.")

        if accounts:
            logging.info(
                "Ejemplo de cuenta API: %s",
                json.dumps(accounts[0], ensure_ascii=False)[:1000],
            )

        insertados = 0
        actualizados = 0

        for acc in accounts:
            # Nombre de la empresa
            name = acc.get("name") or acc.get("account_name")
            if not name:
                continue

            # UDFs reales según el log: "accountudf_fields": {"udf_sline_601": ..., 602, 603}
            udf_fields = acc.get("accountudf_fields") or {}

            def clean(val):
                if val is None:
                    return None
                s = str(val).strip()
                return s or None

            alarms_one_id = clean(
                udf_fields.get("udf_sline_601")
            )
            site24x7_id = clean(
                udf_fields.get("udf_sline_602")
            )
            logs360siem_id = clean(
                udf_fields.get("udf_sline_603")
            )

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

        logging.info(
            f"🏢 Sync empresas completado. Recibidas: {len(accounts)}, "
            f"nuevas: {insertados}, actualizadas: {actualizados}"
        )

    except Exception as e:
        logging.exception(f"❌ Error en tarea_sync_empresas: {e}")


# === NUEVA TAREA: Sync user_groups Site24x7 → Client.site24x7_user_groups (por email) ===
@shared_task
def tarea_sync_site24x7_user_groups():
    """
    Llama a la API de Site24x7 (/api/users) y, para cada usuario devuelto,
    busca un Client por email (email_address) y guarda sus user_groups
    en el campo Client.site24x7_user_group (como string separado por comas).
    """
    try:
        logging.info("👤 [Site24x7] Llamando a https://www.site24x7.com/api/users ...")

        token = "1000.5febf424df5d8b94712cd77f10e8a50c.daf8ae8b9f5a498afa9c2ffb61e6a1b8"
        if not token:
            logging.error("❌ [Site24x7] Falta SITE24X7_OAUTH_TOKEN en variables de entorno.")
            return

        headers = {
            "Accept": "application/json; version=2.0",
            "Authorization": f"Zoho-oauthtoken {token}",
        }

        with httpx.Client(timeout=30) as client:
            resp = client.get("https://www.site24x7.com/api/users", headers=headers)
            resp.raise_for_status()
            data = resp.json()

        users = (data or {}).get("data", []) or []
        logging.info("👤 [Site24x7] Recibidos %s usuarios desde la API.", len(users))

        actualizados = 0
        sin_cliente = 0
        sin_email = 0

        for u in users:
            email = u.get("email_address")
            if not email:
                sin_email += 1
                continue

            user_groups = u.get("user_groups") or []
            # los guardamos como string "id1,id2,id3"
            groups_str = ",".join(str(g) for g in user_groups) if user_groups else None

            try:
                client_obj = Client.objects.filter(email__iexact=email).first()
            except Exception as e:
                logging.exception(
                    "❌ [Site24x7] Error buscando Client por email=%s: %s", email, e
                )
                continue

            if not client_obj:
                sin_cliente += 1
                logging.info(
                    "👤 [Site24x7] No se encontró Client con email=%s para user_id=%s",
                    email,
                    u.get("user_id"),
                )
                continue

            # 👈 AQUÍ el nombre correcto del campo es site24x7_user_group (singular)
            if client_obj.site24x7_user_group != groups_str:
                client_obj.site24x7_user_group = groups_str
                client_obj.save(update_fields=["site24x7_user_group"])
                actualizados += 1

        logging.info(
            "👤 [Site24x7] tarea_sync_site24x7_user_groups completada. "
            "Clientes actualizados=%s, sin_cliente=%s, sin_email=%s",
            actualizados,
            sin_cliente,
            sin_email,
        )

    except Exception as e:
        logging.exception("❌ [Site24x7] Error en tarea_sync_site24x7_user_groups: %s", e)
        return