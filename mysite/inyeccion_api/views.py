# mysite/dashboard/views.py
import json, re, csv, io
from datetime import datetime, timedelta, timezone

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse, HttpResponseBadRequest
from dateutil.parser import isoparse
import pytz
from django.db import transaction
from .models import Alarm
from integrations.alarmsone import list_alarms, list_alarms_all

# -----------------------------
# Columnas visibles (orden):
# - 4 del payload plano
# - 2 derivadas desde message/log_details: Severity y Device Name
# - + eventtime (ms->datetime) y alarmid (id API)
# -----------------------------
_WHITELIST_ORDERED = [
    "Action", "actions", "aotags", "severity",
    "msg_severity", "msg_device_name", "eventtime", "alarmid",
]

# CSV injection guard (Excel)
_CSV_INJECTION = re.compile(r'^[=\+\-@]')

# -----------------------------
# Helpers
# -----------------------------
def _parse_iso(value, default):
    try:
        return isoparse(value)
    except Exception:
        return default

def _cell(v):
    if v is None:
        return ""
    if isinstance(v, (dict, list)):
        return json.dumps(v, ensure_ascii=False)
    return str(v)

def _safe_csv(v):
    s = _cell(v)
    return "'" + s if _CSV_INJECTION.match(s) else s

def _get_value_case_insensitive(d: dict, key: str):
    """Busca key en dict respetando el payload (case-insensitive)."""
    if not isinstance(d, dict):
        return ""
    if key in d:
        return d[key]
    kl = key.lower()
    for k, v in d.items():
        if isinstance(k, str) and k.lower() == kl:
            return v
    return ""

# --- Parser robusto para bloques HTML/JSON en 'message' o 'log_details' ---
_KEYVAL_ROW_REGEX = re.compile(
    r"<td[^>]*>\s*([^:<][^<]*?)\s*</td>\s*<td[^>]*>\s*([^<]*?)\s*</td>",
    flags=re.I,
)
_LINE_REGEX = re.compile(r"^\s*([^:]{1,64})\s*:\s*(.+)\s*$")

def _norm_key(s: str) -> str:
    if not isinstance(s, str):
        return ""
    s = s.replace("\xa0", " ")
    s = re.sub(r"\s+", " ", s.strip())
    return s.lower()

def _extract_kv_from_any(raw_block) -> dict:
    if not raw_block:
        return {}
    if isinstance(raw_block, dict):
        return { _norm_key(k): _cell(v) for k, v in raw_block.items() if isinstance(k, str) }

    s = str(raw_block)

    try:
        obj = json.loads(s)
        if isinstance(obj, dict):
            return { _norm_key(k): _cell(v) for k, v in obj.items() if isinstance(k, str) }
    except Exception:
        pass

    pairs = {}
    for k, v in _KEYVAL_ROW_REGEX.findall(s):
        pairs[_norm_key(k)] = v.strip()
    if pairs:
        return pairs

    kv = {}
    for line in s.splitlines():
        m = _LINE_REGEX.match(line)
        if m:
            kv[_norm_key(m.group(1))] = m.group(2).strip()
    return kv

def _message_extract_multiple_sources(alarm: dict, wanted: list[str]) -> dict:
    detail_keys_candidates = ["log_details", "logdetail", "log-details", "log detail", "logdetails"]

    merged = {}
    for dk in detail_keys_candidates:
        block = _get_value_case_insensitive(alarm, dk)
        d = _extract_kv_from_any(block)
        if d:
            merged.update(d)

    msg_block = _get_value_case_insensitive(alarm, "message")
    dmsg = _extract_kv_from_any(msg_block)
    merged.update(dmsg)

    out = {w: "" for w in wanted}
    for w in wanted:
        k = _norm_key(w)
        val = merged.get(k, "")
        if not val and k == "device name":
            val = merged.get("device name", "") or merged.get("device", "") or merged.get("devicename", "")
        out[w] = _cell(val)
    return out

def _to_datetime_santiago(timestamp_ms) -> datetime | None:
    """Convierte epoch ms -> datetime en America/Santiago (con tz)."""
    if not timestamp_ms:
        return None
    try:
        ts_s = int(timestamp_ms) / 1000
        utc_dt = datetime.fromtimestamp(ts_s, tz=pytz.utc)
        return utc_dt.astimezone(pytz.timezone("America/Santiago"))
    except (ValueError, TypeError):
        return None

def _format_aotags(value) -> str:
    """Normaliza aotags a 'tag1, tag2'."""
    if not value:
        return ""
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            cleaned = value.strip().strip('[]"')
            return cleaned if cleaned else ""
    if isinstance(value, list):
        return ", ".join(str(t).strip() for t in value if isinstance(t, str) and t.strip())
    return str(value)

def _value_for_column(alarm: dict, column: str):
    """Obtiene el valor para cada columna visible."""
    if column in ("Action", "actions", "severity", "alarmid"):
        return _get_value_case_insensitive(alarm, column)

    if column == "eventtime":
        return _to_datetime_santiago(_get_value_case_insensitive(alarm, column))

    if column == "aotags":
        return _format_aotags(_get_value_case_insensitive(alarm, column))

    if column in ("msg_severity", "msg_device_name"):
        extracted = _message_extract_multiple_sources(
            alarm, wanted=["Severity", "Device Name", "Device"]
        )
        if column == "msg_severity":
            return extracted.get("Severity", "") or ""
        if column == "msg_device_name":
            return extracted.get("Device Name", "") or extracted.get("Device", "") or ""
    return ""

# -----------------------------
# Mapeo API -> Modelo + Sync a BD
# -----------------------------
def _map_api_alarm_to_model(a: dict) -> Alarm | None:
    """
    Construye un objeto Alarm (no guardado) desde un dict de la API.
    Usa alertid (o alarmid) como clave única.
    """
    raw_alertid = (
        _get_value_case_insensitive(a, "alertid")
        or _get_value_case_insensitive(a, "alarmid")
        or _get_value_case_insensitive(a, "Alertid")  # por si viene en otro casing
    )
    if not raw_alertid:
        return None

    event_time = _to_datetime_santiago(_get_value_case_insensitive(a, "eventtime"))
    tags = _format_aotags(_get_value_case_insensitive(a, "aotags"))
    severity = _get_value_case_insensitive(a, "severity") or ""
    action = _get_value_case_insensitive(a, "Action") or ""
    actions = _get_value_case_insensitive(a, "actions") or ""

    extracted = _message_extract_multiple_sources(a, ["Device Name", "Device", "Severity"])
    device_name = extracted.get("Device Name", "") or extracted.get("Device", "") or ""

    return Alarm(
        alertid=str(raw_alertid),
        event_time=event_time,
        tags=tags,
        severity=severity,
        device_name=device_name,
        action=action,
        actions=actions,
    )

@transaction.atomic
def _sync_replace_table(alarms_from_api: list[dict]) -> tuple[int, int]:
    """
    BORRA toda la tabla Alarm y hace bulk_insert de lo nuevo.
    Devuelve (insertados, ignorados).
    """
    # Borrar todo
    Alarm.objects.all().delete()

    # Mapear y filtrar nulos
    objects = []
    ignored = 0
    for a in alarms_from_api:
        obj = _map_api_alarm_to_model(a)
        if obj is None:
            ignored += 1
        else:
            objects.append(obj)

    # Insertar por lotes
    inserted = 0
    BATCH = 1000
    for i in range(0, len(objects), BATCH):
        batch = objects[i:i+BATCH]
        Alarm.objects.bulk_create(batch, batch_size=BATCH)
        inserted += len(batch)

    return inserted, ignored

# -----------------------------
# Views
# -----------------------------
@login_required
def inyeccion_api_view(request):
    return HttpResponse(
        f"Inyeccion API OK. Hola {request.user.username}! "
        f"<a href='/inyeccion_api/alarms/preview'>Probar API</a> | "
        f"<a href='/inyeccion_api/alarms/'>Ver tabla</a>"
    )

@login_required
def alarms_preview(request):
    now = datetime.now(timezone.utc)
    dt_from = _parse_iso(request.GET.get("from", ""), now - timedelta(days=7))
    dt_to   = _parse_iso(request.GET.get("to", ""),   now)
    status  = request.GET.get("status", "all")
    size    = int(request.GET.get("size", "10"))
    start   = int(request.GET.get("start", "0"))

    try:
        raw, final_url = list_alarms(
            from_dt=dt_from, to_dt=dt_to,
            status=status, size=size, start=start
        )
        data = raw.get("data") or raw
        return JsonResponse({"ok": True, "url": final_url, "data": data}, json_dumps_params={"indent": 2})
    except Exception as e:
        return HttpResponseBadRequest(f"Error AlarmsOne: {e}")

@login_required
def alarms_table(request):
    """
    1) Sincroniza SIEMPRE la tabla Alarm con la API (borra e inserta).
    2) Renderiza la tabla HTML con las columnas pedidas.
    """
    now = datetime.now(timezone.utc)

    # Parámetros de descarga
    dt_from = _parse_iso(request.GET.get("from",""), now - timedelta(days=int(request.GET.get("days","7"))))
    dt_to   = _parse_iso(request.GET.get("to",""),   now)
    status  = request.GET.get("status","all")
    page_sz = int(request.GET.get("page_size","10000"))
    pages   = int(request.GET.get("pages","1"))
    q       = request.GET.get("q")
    search  = {"searchItems":[{"field":"_all","value": q}]} if q else None

    # 1) Traer de la API
    try:
        result = list_alarms_all(
            from_dt=dt_from, to_dt=dt_to, status=status,
            page_size=page_sz, max_pages=pages, search_json=search
        )
        alarms_api = result["alarms"]
    except Exception as e:
        return HttpResponseBadRequest(f"Error consultando API: {e}")

    # 2) Sincronizar BD (drop + bulk insert)
    try:
        inserted, ignored = _sync_replace_table(alarms_api)
    except Exception as e:
        return HttpResponseBadRequest(f"Error sincronizando BD: {type(e).__name__}: {e}")

    # 3) Preparar datos para render (desde API para no volver a consultar BD)
    cols = _WHITELIST_ORDERED
    rows = [[_cell(_value_for_column(a, c)) for c in cols] for a in alarms_api]

    qs_str = request.META.get("QUERY_STRING","")

    html = [
        "<!doctype html><html><head><meta charset='utf-8'>",
        "<title>AlarmsOne (sync + tabla)</title>",
        "<style>",
        "body{font-family:sans-serif;margin:16px}",
        "table{border-collapse:collapse;width:100%}",
        "th,td{border:1px solid #ddd;padding:6px;vertical-align:top}",
        "th{background:#f5f5f5;text-align:left}",
        "h2{color:#333}",
        "a.btn{display:inline-block;margin:8px 0;padding:6px 10px;border:1px solid #444;border-radius:8px;text-decoration:none;color:#111}",
        "</style></head><body>"
    ]

    html.append(f"""
        <h2>AlarmsOne — {len(alarms_api)} filas</h2>
        <p>Sync: insertados <b>{inserted}</b>, ignorados <b>{ignored}</b>. (Tabla BD reemplazada)</p>
        <p>Filtro aplicado: {qs_str}</p>
        <p>Columnas: <strong>{", ".join(cols)}</strong></p>
        <a class='btn' href='/inyeccion_api/alarms/export.csv?{qs_str}' target='_blank'>Exportar CSV</a>
    """)

    html.append("<table><thead><tr>" + "".join(f"<th>{c}</th>" for c in cols) + "</tr></thead><tbody>")
    for r in rows:
        html.append("<tr>" + "".join(f"<td>{v}</td>" for v in r) + "</tr>")
    html.append("</tbody></table>")
    html.append("</body></html>")

    return HttpResponse("".join(html))

@login_required
def alarms_export_csv(request):
    """
    Exporta las columnas visibles (con los mismos filtros de descarga).
    NOTE: exporta desde la API para que coincida con la tabla recién renderizada.
    """
    now = datetime.now(timezone.utc)
    dt_from = _parse_iso(request.GET.get("from",""), now - timedelta(days=int(request.GET.get("days","7"))))
    dt_to   = _parse_iso(request.GET.get("to",""),   now)
    status  = request.GET.get("status","all")
    page_sz = int(request.GET.get("page_size","200"))
    pages   = int(request.GET.get("pages","1"))
    q       = request.GET.get("q")
    search  = {"searchItems":[{"field":"_all","value": q}]} if q else None

    try:
        result = list_alarms_all(
            from_dt=dt_from, to_dt=dt_to, status=status,
            page_size=page_sz, max_pages=pages, search_json=search
        )
        alarms = result["alarms"]
        if not alarms:
            return HttpResponse("No hay resultados.", content_type="text/plain; charset=utf-8")

        cols = _WHITELIST_ORDERED
        buff = io.StringIO()
        buff.write("\ufeff")
        w = csv.writer(buff)
        w.writerow(cols)

        for a in alarms:
            row = []
            for c in cols:
                v = _value_for_column(a, c)
                row.append(_safe_csv(v))
            w.writerow(row)

        resp = HttpResponse(buff.getvalue(), content_type="text/csv; charset=utf-8")
        resp["Content-Disposition"] = 'attachment; filename=\"alarms_export_with_message.csv\"'
        return resp
    except Exception as e:
        return HttpResponseBadRequest(f"Error AlarmsOne: {e}")
