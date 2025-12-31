from __future__ import annotations

import json
import logging
import re
import subprocess
from datetime import datetime, timezone as _pytimezone

import httpx
import pytz
from django.contrib.auth.decorators import login_required
from django.http import (
    HttpResponseBadRequest,
    HttpResponseRedirect,
    JsonResponse,
)
from django.shortcuts import render
from django.urls import NoReverseMatch, reverse
from django.utils.html import escape
from tenants.decorators import tenant_required, service_required
from tenants.models import Tenant
from django.views.decorators.http import require_GET
from home.models import TenantCredentials, WhitelistCountryPreference
from home.countries import ALL_COUNTRIES


from .realtime_transform import build_realtime_context

logger = logging.getLogger(__name__)

# ================== RANGO HOY ==================


def _today_range_ms_scl():
    tz = pytz.timezone("America/Santiago")
    now_local = datetime.now(tz)
    start_local = tz.localize(
        datetime(now_local.year, now_local.month, now_local.day, 0, 0, 0)
    )
    start_utc = start_local.astimezone(_pytimezone.utc)
    now_utc = now_local.astimezone(_pytimezone.utc)
    return int(start_utc.timestamp() * 1000), int(now_utc.timestamp() * 1000)


# ================= TOKEN / FETCH ================


def _get_token_via_script_local():
    """
    Ejecuta obtener_token.py y devuelve el token por stdout.

    FIX: este flujo (Realtime / AlarmsOne) debe usar el PRIMER token del webhook.
    Para no romper otros flujos que usan el segundo, le pedimos explícitamente
    --index 0 al script.
    """
    script_path = "/home/inntesec-ia/Proyecto-Dashboard/obtener_token.py"

    try:
        out = subprocess.run(
            ["python3", script_path, "--index", "0"],  # ✅ PRIMER token
            capture_output=True,
            text=True,
            timeout=25,
        )
    except Exception as e:
        logger.exception("[REALTIME] Error ejecutando obtener_token.py: %s", e)
        raise RuntimeError(f"Error ejecutando obtener_token.py: {e}") from e

    if out.returncode != 0:
        logger.error(
            "[REALTIME] obtener_token.py falló exit=%s stderr=%s",
            out.returncode,
            (out.stderr or out.stdout),
        )
        raise RuntimeError(
            f"obtener_token.py exit={out.returncode} stderr={out.stderr or out.stdout}"
        )

    token = (out.stdout or "").strip()
    if not token:
        logger.error(
            "[REALTIME] obtener_token.py devolvió stdout vacío. stderr=%s",
            out.stderr,
        )
        raise RuntimeError("obtener_token.py devolvió vacío")

    return token


def _fetch_alarms_today_direct(max_pages=50, page_size=1000):
    token = _get_token_via_script_local()
    headers = {"Authorization": f"Zoho-oauthtoken {token}"}
    from_ms, to_ms = _today_range_ms_scl()

    base = "https://alarmsone.manageengine.com/rest/json/listAlarms"
    all_rows, offset = [], 0
    for _ in range(max_pages):
        url = (
            f"{base}?fromDate={from_ms}&toDate={to_ms}"
            f"&filter=all&size={page_size}&from={offset}"
        )
        with httpx.Client(timeout=30) as client:
            r = client.get(url, headers=headers)
            r.raise_for_status()
            payload = r.json() or {}
        rows = payload.get("data") or payload.get("alarms") or []
        if not isinstance(rows, list):
            rows = []
        if not rows:
            break
        all_rows.extend(rows)
        if len(rows) < page_size:
            break
        offset += page_size
    return from_ms, to_ms, all_rows


# ========== HELPERS GENERALES ==========


def _get_value_case_insensitive(d: dict, key: str):
    if not isinstance(d, dict):
        return ""
    if key in d:
        return d[key]
    kl = key.lower()
    for k, val in d.items():
        if isinstance(k, str) and k.lower() == kl:
            return val
    return ""


def _to_datetime_santiago(timestamp_ms):
    if not timestamp_ms:
        return ""
    try:
        ts_s = int(timestamp_ms) / 1000
        utc_dt = datetime.fromtimestamp(ts_s, tz=pytz.utc)
        return utc_dt.astimezone(pytz.timezone("America/Santiago"))
    except Exception:
        return ""


_KEYVAL_ROW_REGEX = re.compile(
    r"<td[^>]*>\s*([^:<][^<]*?)\s*</td>\s*"
    r"<td[^>]*>\s*([\s\S]*?)\s*</td>",
    re.I,
)
_LINE_REGEX = re.compile(r"^\s*([^:]{1,64})\s*:\s*(.+)\s*$")


def _strip_html(s: str) -> str:
    s = re.sub(r"<[^>]+>", "", s or "", flags=re.I)
    return re.sub(r"\s+", " ", s).strip()


def _norm_key(s: str) -> str:
    if not isinstance(s, str):
        return ""
    s = s.replace("\xa0", " ")
    s = re.sub(r"\s+", " ", s.strip())
    return s.lower()


def _extract_kv_generic(raw_block) -> dict:
    """
    Parser genérico para:
      - dicts
      - JSON
      - tablas HTML (FortiAnalyzer)
      - líneas 'key: value'
      - línea larga tipo Log360 'key=value key2=value2 ...'
    """
    if not raw_block:
        return {}

    # dict directo
    if isinstance(raw_block, dict):
        return {
            _norm_key(k): _strip_html(str(v))
            for k, v in raw_block.items()
            if isinstance(k, str)
        }

    s = str(raw_block)

    # 1) Intentar JSON
    try:
        obj = json.loads(s)
        if isinstance(obj, dict):
            return {
                _norm_key(k): _strip_html(str(v))
                for k, v in obj.items()
            }
    except Exception:
        pass

    # 2) Tablas HTML FortiAnalyzer
    pairs: dict[str, str] = {}
    for k, vv in _KEYVAL_ROW_REGEX.findall(s):
        key = _norm_key(k)
        val = _strip_html(vv)
        pairs[key] = val
    if pairs:
        return pairs

    # 3) Formato "key: value"
    kv: dict[str, str] = {}
    for line in s.splitlines():
        m = _LINE_REGEX.match(line)
        if m:
            key = _norm_key(m.group(1))
            val = _strip_html(m.group(2))
            kv[key] = val

    # 4) Formato "key=value" (Log360)
    if "=" in s:
        clean = _strip_html(s)
        for token in clean.replace("\n", " ").split(" "):
            if "=" in token:
                try:
                    k, v = token.split("=", 1)
                    k = _norm_key(k)
                    v = v.strip().strip('"')
                    if k:
                        kv[k] = v
                except Exception:
                    pass

    # fallback para Log Description si viene embebido
    if "log description" not in kv:
        m = re.search(
            r"log description[:\-]\s*([\s\S]+?)(?:<|$)",
            s,
            re.I,
        )
        if m:
            kv["log description"] = _strip_html(m.group(1))

    return kv


def _message_extract_multiple_sources(alarm: dict, wanted: list[str]) -> dict:
    """
    Combina info tanto de 'log_details' como de 'message',
    normalizando claves y devolviendo solo las pedidas en 'wanted'.
    Aplica la misma lógica de severidad que en el JS:
    severity / Severity / severity2 / level.
    """
    detail_keys_candidates = [
        "log_details",
        "logdetail",
        "log-details",
        "log detail",
        "logdetails",
    ]
    merged: dict[str, str] = {}

    for dk in detail_keys_candidates:
        block = _get_value_case_insensitive(alarm, dk)
        d = _extract_kv_generic(block)
        if d:
            merged.update(d)

    msg_block = _get_value_case_insensitive(alarm, "message")
    dmsg = _extract_kv_generic(msg_block)
    if dmsg:
        merged.update(dmsg)

    # Aliases
    device_aliases = ["device name", "device", "devicename", "devname"]
    subtype_aliases = ["subtype", "sub type"]
    severity_aliases = ["severity", "severity2", "level"]

    out = {w: "" for w in wanted}
    for w in wanted:
        k = _norm_key(w)
        val = merged.get(k, "")

        # Device name
        if not val and k == "device name":
            for ak in device_aliases:
                if merged.get(ak):
                    val = merged[ak]
                    break

        # Subtype
        if not val and k == "subtype":
            for ak in subtype_aliases:
                if merged.get(ak):
                    val = merged[ak]
                    break

        # Severity (misma lógica que en n8n)
        if not val and k == "severity":
            for ak in severity_aliases:
                if merged.get(ak):
                    val = merged[ak]
                    break

        out[w] = val or ""

    return out


def value_for_column(alarm: dict, column: str):
    """
    Resolver valores para columnas usadas en realtime/dashboard
    (compatible con views._value_for_column, pero local).
    """
    if column in ("Action", "actions", "severity", "alarmid"):
        return _get_value_case_insensitive(alarm, column)

    if column == "eventtime":
        return _to_datetime_santiago(
            _get_value_case_insensitive(alarm, column)
        )

    if column == "aotags":
        return _get_value_case_insensitive(alarm, column)

    if column in (
        "msg_severity",
        "msg_device_name",
        "level",
        "log_description",
        "subtype",
    ):
        extracted = _message_extract_multiple_sources(
            alarm,
            wanted=[
                "Severity",
                "Device Name",
                "Device",
                "Level",
                "Log Description",
                "Subtype",
            ],
        )
        if column == "msg_severity":
            return extracted.get("Severity", "") or ""
        if column == "msg_device_name":
            return (
                extracted.get("Device Name", "")
                or extracted.get("Device", "")
                or ""
            )
        if column == "level":
            return extracted.get("Level", "") or ""
        if column == "log_description":
            return extracted.get("Log Description", "") or ""
        if column == "subtype":
            return extracted.get("Subtype", "") or ""

    return ""


# ========== AOTAGS / TENANT ==========


def _format_aotags(value) -> str:
    if not value:
        return ""
    if isinstance(value, str):
        s = value.strip()
        try:
            obj = json.loads(s)
            value = obj
        except json.JSONDecodeError:
            cleaned = s.strip().strip('[]\"')
            return cleaned if cleaned else ""
    if isinstance(value, list):
        return ", ".join(
            str(t).strip()
            for t in value
            if isinstance(t, (str, int)) and str(t).strip()
        )
    return str(value)


def _aotags_to_list(value) -> list[str]:
    s = _format_aotags(value)
    if not s:
        return []
    parts = [p.strip() for p in s.split(",")]
    return [p.lower() for p in parts if p]


def _filter_for_request_tenant(request, alarms: list[dict]) -> list[dict]:
    tenant = getattr(request, "tenant", None)
    if not tenant:
        logger.warning("[Realtime] request sin tenant → 0 alarmas")
        return []
    aotag = (getattr(tenant, "alarms_one_id", "") or "").strip().lower()
    if not aotag:
        logger.warning(
            "[Realtime] tenant '%s' sin alarms_one_id → 0 alarmas",
            getattr(tenant, "name", "?"),
        )
        return []
    filtered = []
    for a in (alarms or []):
        tags_raw = _get_value_case_insensitive(a, "aotags")
        taglist = _aotags_to_list(tags_raw)
        if aotag in taglist:
            a["aotags"] = _format_aotags(tags_raw)
            filtered.append(a)
    return filtered


# =================== PAGE ===================


@login_required
@tenant_required
@service_required("alarms_one_id")
def realtime_page(request):
    tenant = getattr(request, "tenant", None)

    try:
        try:
            hist_url = reverse("dashboard_alarmsone")
        except NoReverseMatch:
            hist_url = "/dashboard/alarmsone/"
    except Exception:
        hist_url = "/dashboard/alarmsone/"

    # Valores por defecto (por si hay error)
    ctx: dict = {}
    kpi_total = 0
    kpi_high = 0
    kpi_dev = 0
    error_public: str | None = None

    # Intentar obtener alarmas en tiempo real
    try:
        _, _, alarms = _fetch_alarms_today_direct()
        alarms = _filter_for_request_tenant(request, alarms)
        ctx = build_realtime_context(
            alarms, value_for_column, tzname="America/Santiago"
        )

        # Totales
        kpi_total = sum(ctx.get("severity_counts", {}).values())
        msgsev = ctx.get("msg_severity_counts", {}) or {}
        kpi_high = int(msgsev.get("critical", 0))
        kpi_dev = len(ctx.get("device_counts", {}))

    except Exception as e:
        # Incluye errores de token, 401/403, etc.
        logger.exception(
            "[REALTIME] Error construyendo dashboard realtime: %s",
            e,
        )
        error_public = (
            "No fue posible obtener las alarmas en tiempo real para este tenant."
        )
        # ctx queda vacío y KPIs en 0 → el template entra en el bloque de 'error'

    # Credenciales activas del tenant
    cred = None
    try:
        if tenant:
            cred = TenantCredentials.get_active_for_tenant(
                int(getattr(tenant, "id", 0))
            )
    except Exception as e:
        logger.exception(
            "[REALTIME] Error obteniendo credenciales del tenant: %s",
            e,
        )

    # Selector de tenants para Inntesec (según el tenant del USUARIO, no el activo)
    tenants_list = []
    try:
        base_tenant = getattr(request.user, "tenant", None)
        if base_tenant and base_tenant.name.lower() == "inntesec":
            tenants_list = Tenant.objects.all().order_by("name")
    except Exception:
        tenants_list = []

    # Países para el modal de whitelist
    selected_paises = []
    try:
        pref = WhitelistCountryPreference.objects.get(user=request.user)
        selected_paises = pref.paises or []
    except WhitelistCountryPreference.DoesNotExist:
        selected_paises = []
    except Exception as e:
        logger.exception(
            "[REALTIME] Error leyendo preferencias de países: %s", e
        )
        selected_paises = []

    page_ctx = {
        "tenant": tenant,
        "hist_url": hist_url,
        "kpi_total": kpi_total,
        "kpi_high": kpi_high,
        "kpi_dispositivos": kpi_dev,
        "all_tenants": tenants_list,
        "cred": cred,
        "whitelist_countries": ALL_COUNTRIES,
        "selected_paises": selected_paises,
        # error genérico para el template (None si todo OK)
        "error": error_public,
        # contexto realtime original
        **ctx,
    }
    return render(request, "dashboard/realtime.html", page_ctx)


@login_required
@tenant_required
@service_required("alarms_one_id")
def realtime_data(request):
    """
    Endpoint JSON para refrescar datos realtime desde el frontend.
    En caso de error retorna ok=False con mensaje genérico.
    """
    try:
        _, _, alarms = _fetch_alarms_today_direct()
        alarms = _filter_for_request_tenant(request, alarms)
        ctx = build_realtime_context(
            alarms, value_for_column, tzname="America/Santiago"
        )
        return JsonResponse({"ok": True, "data": ctx}, json_dumps_params={"indent": 2})
    except Exception as e:
        logger.exception("[REALTIME] realtime_data error: %s", e)
        return JsonResponse(
            {
                "ok": False,
                "error": (
                    "No fue posible obtener los datos de tiempo real en este momento. "
                    "Por favor, contacte con un administrador."
                ),
            },
            status=502,
        )


# ================== HELPERS FILTRO (AND exacto) ==================


def _lc(s):
    return str(s or "").strip().lower()


def _eq_ci(a, b):
    return _lc(a) == _lc(b)


def _in_ci(val, population):
    v = _lc(val)
    return any(_lc(x) == v for x in (population or []))


def _split_list_param(raw):
    if raw is None:
        return []
    s = str(raw).strip()
    if not s:
        return []
    try:
        obj = json.loads(s)
        if isinstance(obj, list):
            return [str(x).strip() for x in obj if str(x).strip()]
    except Exception:
        pass
    if "," in s:
        parts = s.split(",")
    elif "|" in s:
        parts = s.split("|")
    else:
        parts = [s]
    return [p.strip() for p in parts if p.strip()]


def _hour_str_from_alarm(alarm):
    dt = value_for_column(alarm, "eventtime")
    if isinstance(dt, datetime):
        return f"{dt.hour:02d}"
    try:
        ms = int(_get_value_case_insensitive(alarm, "eventtime"))
        tz = pytz.timezone("America/Santiago")
        hh = (
            datetime.fromtimestamp(ms / 1000.0, tz=pytz.utc)
            .astimezone(tz)
            .hour
        )
        return f"{hh:02d}"
    except Exception:
        return ""


def _apply_query_filters(request, alarms):
    q = request.GET
    f_action = q.get("action", "")
    f_severity = _lc(q.get("severity", ""))
    f_msgsev = _lc(q.get("msg_severity", ""))
    f_level = q.get("level", "")
    f_device = q.get("device", "")
    f_hour = q.get("hour", "")
    f_hours_many = _split_list_param(q.get("hours"))
    f_subtype_one = q.get("subtype", "")
    f_subtypes_many = _split_list_param(q.get("subtypes"))

    hours_set = {str(int(h)).zfill(2) for h in f_hours_many if str(h).isdigit()}

    out = []
    for a in alarms:
        act = value_for_column(a, "actions") or value_for_column(a, "Action")
        sev = _lc(value_for_column(a, "severity"))
        msg = _lc(value_for_column(a, "msg_severity"))
        lvl = value_for_column(a, "level")
        dev = value_for_column(a, "msg_device_name") or value_for_column(
            a, "device"
        )
        stp = value_for_column(a, "subtype")
        hh = _hour_str_from_alarm(a)

        if f_action and not _eq_ci(act, f_action):
            continue
        if f_severity and sev != f_severity:
            continue
        if f_msgsev and msg != f_msgsev:
            continue
        if f_level and not _eq_ci(lvl, f_level):
            continue
        if f_device and not _eq_ci(dev, f_device):
            continue
        if f_hour and hh != str(f_hour).zfill(2):
            continue
        if hours_set and hh not in hours_set:
            continue
        if f_subtype_one and not _eq_ci(stp, f_subtype_one):
            continue
        if f_subtypes_many and not _in_ci(stp, f_subtypes_many):
            continue

        out.append(a)
    return out


# ================== ENDPOINT: LISTA ALARMAS ==================

@require_GET
@login_required
@tenant_required
@service_required("alarms_one_id")
def realtime_alarms_by_subtype(request):
    try:
        _, _, alarms = _fetch_alarms_today_direct()
        alarms = _filter_for_request_tenant(request, alarms)
        alarms = _apply_query_filters(request, alarms)

        rows_out = []
        for a in alarms:
            ext = _message_extract_multiple_sources(
                a,
                wanted=[
                    "Severity",
                    "Device Name",
                    "Device",
                    "Level",
                    "Log Description",
                    "Subtype",
                ],
            )
            dt = value_for_column(a, "eventtime")
            rows_out.append(
                {
                    "alarmid": _get_value_case_insensitive(a, "alarmid"),
                    "eventtime": dt.isoformat()
                    if isinstance(dt, datetime)
                    else str(dt or ""),
                    "severity": _lc(value_for_column(a, "severity")),
                    "msg_severity": _lc(ext.get("Severity") or ""),
                    "device": (
                        ext.get("Device Name") or ext.get("Device") or ""
                    ).strip(),
                    "level": (ext.get("Level") or "").strip(),
                    "action": _get_value_case_insensitive(a, "actions")
                    or _get_value_case_insensitive(a, "Action"),
                    "subtype": (ext.get("Subtype") or "").strip(),
                    "log_description": (ext.get("Log Description") or "").strip(),
                }
            )

        rows_out.sort(key=lambda r: r.get("eventtime", ""), reverse=True)
        return JsonResponse(
            {"ok": True, "count": len(rows_out), "rows": rows_out[:1000]},
            json_dumps_params={"indent": 2},
        )
    except Exception as e:
        logger.exception("[REALTIME] realtime_alarms_by_subtype error: %s", e)
        return JsonResponse(
            {
                "ok": False,
                "error": (
                    "No fue posible obtener el listado de alarmas en tiempo real. "
                    "Por favor, contacte con un administrador."
                ),
            },
            status=502,
        )


# ================== ENDPOINT: LOG (DETALLE) ==================

@require_GET
@login_required
@tenant_required
@service_required("alarms_one_id")
def realtime_alarm_log_table(request):
    """
    Devuelve el HTML del detalle de log.

    - Si `message` (o `log_details`) ya trae una tabla HTML → se usa tal cual.
    - Si NO trae tabla:
        * Se parsea SOLO el campo `message` (formato key=value, etc.).
        * Se arma una tabla con estilo similar a FortiAnalyzer:
          encabezado "Log Details:" y filas clave/valor sin cabecera "Campo / Valor".
    """
    try:
        alarmid = request.GET.get("alarmid") or request.GET.get("alarm_id")
        if not alarmid:
            return HttpResponseBadRequest("Falta alarmid")

        _, _, alarms = _fetch_alarms_today_direct()
        alarms = _filter_for_request_tenant(request, alarms)

        found = None
        for a in alarms:
            aid = _get_value_case_insensitive(a, "alarmid")
            if str(aid) == str(alarmid):
                found = a
                break

        if not found:
            return JsonResponse(
                {"ok": False, "html": "<em>Alarma no encontrada</em>"}
            )

        raw_msg = _get_value_case_insensitive(found, "message")
        raw_logdetails = _get_value_case_insensitive(found, "log_details")

        html = ""

        # 1) Si el propio message ya trae tabla HTML → usarla
        if isinstance(raw_msg, str) and "<table" in raw_msg.lower():
            html = raw_msg
        # 2) Si no, pero log_details trae tabla HTML → usar esa
        elif isinstance(raw_logdetails, str) and "<table" in raw_logdetails.lower():
            html = raw_logdetails
        else:
            # 3) Construir tabla "Log Details" SOLO desde message
            kv = _extract_kv_generic(raw_msg)

            # Si no logramos nada desde message, probamos log_details como fallback
            if not kv and raw_logdetails:
                kv = _extract_kv_generic(raw_logdetails)

            rows = []
            if kv:
                for idx, (k, v) in enumerate(kv.items()):
                    bg = "#EDF5FF" if idx % 2 == 0 else "#FFFFFF"
                    ks = escape(str(k))
                    vs = escape(str(v))
                    rows.append(
                        f"<tr bgcolor=\"{bg}\">"
                        f"<td width=\"20%\">{ks}</td>"
                        f"<td width=\"80%\"><pre>{vs}</pre></td>"
                        "</tr>"
                    )

                html = (
                    "<div style=\"margin-top:12px;margin-bottom:4px;\">"
                    "Log Details:"
                    "</div>"
                    "<table border=\"1\" cellpadding=\"2\" cellspacing=\"0\">"
                    "<tbody>"
                    f"{''.join(rows)}"
                    "</tbody></table>"
                )
            else:
                html = "<em>No se encontraron detalles de log.</em>"

        meta = {
            "alarmid": str(alarmid),
            "severity": str(value_for_column(found, "severity") or ""),
            "msg_severity": str(value_for_column(found, "msg_severity") or ""),
            "device": str(value_for_column(found, "msg_device_name") or ""),
            "level": str(value_for_column(found, "level") or ""),
            "subtype": str(value_for_column(found, "subtype") or ""),
            "action": str(
                value_for_column(found, "actions")
                or value_for_column(found, "Action")
                or ""
            ),
            "eventtime": str(value_for_column(found, "eventtime") or ""),
        }

        return JsonResponse({"ok": True, "meta": meta, "html": html})
    except Exception as e:
        logger.exception("[REALTIME] realtime_alarm_log_table failed: %s", e)
        return JsonResponse(
            {
                "ok": False,
                "error": (
                    "No fue posible obtener el detalle del log en este momento. "
                    "Por favor, contacte con un administrador."
                ),
            },
            status=502,
        )


# ================== SWITCH TENANT ==================


@login_required
def switch_tenant(request, tenant_id: int):
    """Permite cambiar el tenant y redirigir al dashboard realtime."""
    tenant = Tenant.objects.filter(id=tenant_id).first()
    if not tenant:
        return HttpResponseBadRequest("Tenant no encontrado")

    request.session["tenant_id"] = tenant.id
    request.session.modified = True

    try:
        return HttpResponseRedirect(reverse("dashboard_realtime"))
    except Exception:
        return HttpResponseRedirect("/dashboard/realtime/")
