# mysite/dashboard/views.py
import json, re, csv, io
from datetime import datetime, timedelta, timezone

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse, HttpResponseBadRequest
from dateutil.parser import isoparse

from integrations.alarmsone import list_alarms, list_alarms_all

# -----------------------------
# Columnas visibles (orden):
# - 4 del payload plano
# - 2 derivadas desde message/log_details: Severity y Device Name
# -----------------------------
_WHITELIST_ORDERED = [
    "Action", "actions", "aotags", "severity",
    "msg_severity", "msg_device_name", "eventtime",
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
# Captura filas <td>Key</td><td>Value</td> en cualquier tabla (con o sin atributos)
_KEYVAL_ROW_REGEX = re.compile(
    r"<td[^>]*>\s*([^:<][^<]*?)\s*</td>\s*<td[^>]*>\s*([^<]*?)\s*</td>",
    flags=re.I,
)
_LINE_REGEX = re.compile(r"^\s*([^:]{1,64})\s*:\s*(.+)\s*$")

def _norm_key(s: str) -> str:
    # normaliza claves: trim, lower, colapsa espacios, elimina NBSP
    if not isinstance(s, str):
        return ""
    s = s.replace("\xa0", " ")
    s = re.sub(r"\s+", " ", s.strip())
    return s.lower()

def _extract_kv_from_any(raw_block) -> dict:
    """
    Extrae pares key->value de un bloque que puede ser:
    - dict JSON
    - string JSON
    - HTML con tablas <td>Key</td><td>Value</td>
    - texto con líneas 'Key: Value'
    Devuelve un dict con keys normalizadas (lower + espacios colapsados).
    """
    if not raw_block:
        return {}
    # 1) dict directo
    if isinstance(raw_block, dict):
        return { _norm_key(k): _cell(v) for k, v in raw_block.items() if isinstance(k, str) }

    s = str(raw_block)

    # 2) JSON string
    try:
        obj = json.loads(s)
        if isinstance(obj, dict):
            return { _norm_key(k): _cell(v) for k, v in obj.items() if isinstance(k, str) }
    except Exception:
        pass

    # 3) HTML: todas las filas <td>k</td><td>v</td> (puede haber varias tablas)
    pairs = {}
    for k, v in _KEYVAL_ROW_REGEX.findall(s):
        pairs[_norm_key(k)] = v.strip()
    if pairs:
        return pairs

    # 4) Texto plano "Key: Value"
    kv = {}
    for line in s.splitlines():
        m = _LINE_REGEX.match(line)
        if m:
            kv[_norm_key(m.group(1))] = m.group(2).strip()
    return kv

def _message_extract_multiple_sources(alarm: dict, wanted: list[str]) -> dict:
    """
    Busca claves 'wanted' priorizando:
      1) log_details (o variantes) si existen
      2) message
    Si aún faltan claves, intenta alias (p.ej., 'device name' o 'device').
    Devuelve dict con las claves EXACTAS solicitadas (respetando mayúsculas).
    """
    # candidatos de detalle 'largo' comunes en este tipo de payloads
    detail_keys_candidates = ["log_details", "logdetail", "log-details", "log detail", "logdetails"]

    # 1) intenta en log_details (prioridad)
    merged = {}
    for dk in detail_keys_candidates:
        block = _get_value_case_insensitive(alarm, dk)
        d = _extract_kv_from_any(block)
        if d:
            merged.update(d)

    # 2) luego en message (por si alguna clave viene ahí)
    msg_block = _get_value_case_insensitive(alarm, "message")
    dmsg = _extract_kv_from_any(msg_block)
    merged.update(dmsg)

    out = {w: "" for w in wanted}
    for w in wanted:
        k = _norm_key(w)
        val = merged.get(k, "")
        # alias: para 'Device Name', aceptar 'device' como fallback si no hay 'device name'
        if not val and k == "device name":
            val = merged.get("device name", "") or merged.get("device", "")
        # alias extra por si aparece 'devicename' sin espacio
        if not val and k == "device name":
            val = val or merged.get("devicename", "")
        out[w] = _cell(val)
    return out

def _value_for_column(alarm: dict, column: str):
    """
    Obtiene el valor para una columna de la whitelist.
    - Columnas planas: Action/actions/aotags/severity
    - Derivadas: msg_severity, msg_device_name (extraídas desde log_details/message)
    """
    if column in ("Action", "actions", "aotags", "severity", "eventtime"):
        return _get_value_case_insensitive(alarm, column)

    if column in ("msg_severity", "msg_device_name"):
        extracted = _message_extract_multiple_sources(
            alarm, wanted=["Severity", "Device Name", "Device"]
        )
        if column == "msg_severity":
            return extracted.get("Severity", "") or ""
        if column == "msg_device_name":
            # preferimos 'Device Name'; si no, usamos 'Device' (último recurso)
            return extracted.get("Device Name", "") or extracted.get("Device", "") or ""
    return ""

# -----------------------------
# Views
# -----------------------------
@login_required
def dashboard_view(request):
    return HttpResponse(
        f"Dashboard OK. Hola {request.user.username}! "
        f"<a href='/dashboard/alarms/preview'>Probar API</a> | "
        f"<a href='/dashboard/alarms/'>Ver tabla</a>"
    )

@login_required
def alarms_preview(request):
    """
    GET /dashboard/alarms/preview
    Params opcionales:
      ?status=open&size=20&start=0
      ?from=2025-10-01T00:00:00&to=2025-10-15T00:00:00
    """
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
    HTML que muestra columnas:
      Action | actions | aotags | severity | msg_severity | msg_device_name
    Filtros:
      ?days=7&status=open&page_size=200&pages=3&q=texto  ó  ?from=YYYY-MM-DD&to=YYYY-MM-DD
    """
    now = datetime.now(timezone.utc)
    dt_from = _parse_iso(request.GET.get("from",""), now - timedelta(days=int(request.GET.get("days","7"))))
    dt_to   = _parse_iso(request.GET.get("to",""),   now)
    status  = request.GET.get("status","all")
    page_sz = int(request.GET.get("page_size","10000"))
    pages   = int(request.GET.get("pages","1"))
    q       = request.GET.get("q")
    search  = {"searchItems":[{"field":"_all","value": q}]} if q else None

    try:
        result = list_alarms_all(
            from_dt=dt_from, to_dt=dt_to, status=status,
            page_size=page_sz, max_pages=pages, search_json=search
        )
        alarms = result["alarms"]

        cols = _WHITELIST_ORDERED
        rows = [[_cell(_value_for_column(a, c)) for c in cols] for a in alarms]

        qs_str = request.META.get("QUERY_STRING","")

        html = [
            "<!doctype html><html><head><meta charset='utf-8'>",
            "<title>AlarmsOne (vista derivada)</title>",
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
            <h2>AlarmsOne — {len(alarms)} filas</h2>
            <p>Columnas: <strong>{", ".join(cols)}</strong></p>
            <a class='btn' href='/dashboard/alarms/export.csv?{qs_str}' target='_blank'>Exportar CSV</a>
        """)

        html.append("<table><thead><tr>" + "".join(f"<th>{c}</th>" for c in cols) + "</tr></thead><tbody>")
        for r in rows:
            html.append("<tr>" + "".join(f"<td>{v}</td>" for v in r) + "</tr>")
        html.append("</tbody></table>")
        html.append("</body></html>")

        return HttpResponse("".join(html))
    except Exception as e:
        return HttpResponseBadRequest(f"Error AlarmsOne: {e}")

@login_required
def alarms_export_csv(request):
    """
    Exporta las columnas: Action, actions, aotags, severity, msg_severity, msg_device_name
    (mismos filtros que la tabla).
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
        buff.write("\ufeff")  # BOM UTF-8 para Excel
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
