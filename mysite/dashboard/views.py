# dashboard/views.py
import json, re, csv, io
from datetime import datetime, timedelta, timezone

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse, HttpResponseBadRequest
from dateutil.parser import isoparse

# importa AMBAS funciones; usa la que necesites en cada vista
from integrations.alarmsone import list_alarms, list_alarms_all


@login_required
def dashboard_view(request):
    return HttpResponse(
        f"Dashboard OK. Hola {request.user.username}! "
        f"<a href='/dashboard/alarms/preview'>Probar API</a> | "
        f"<a href='/dashboard/alarms/'>Ver tabla</a>"
    )


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
    Página HTML para explorar todas las columnas.
    Útil: ?days=7&status=open&page_size=200&pages=3&q=texto
           o  ?from=2025-10-01&to=2025-10-15
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
        cols = sorted({k for a in alarms for k in a.keys()}) if alarms else []
        rows = [[_cell(a.get(c)) for c in cols] for a in alarms]

        html = ["<!doctype html><html><body>"]

        html.append(f"""
            <h2 style='font-family:sans-serif; color:#333;'>
                Total de alarmas: {len(alarms)}<br>
                Columnas detectadas: {len(cols)}
            </h2>
        """)
        html.append(f"<h3>AlarmsOne — {len(alarms)} filas, {len(cols)} columnas</h3>")
        html.append("<table border='1' cellpadding='4' cellspacing='0'>")
        html.append("<thead><tr>" + "".join(f"<th>{c}</th>" for c in cols) + "</tr></thead><tbody>")
        for r in rows:
            html.append("<tr>" + "".join(f"<td>{v}</td>" for v in r) + "</tr>")
        html.append("</tbody></table>")
        html.append("<p><a href='export.csv'>Exportar CSV (mismos filtros)</a></p>")
        html.append("</body></html>")
        return HttpResponse("".join(html))
    except Exception as e:
        return HttpResponseBadRequest(f"Error AlarmsOne: {e}")

import re  # ya lo tienes arriba, pero por si acaso
_CSV_INJECTION = re.compile(r'^[=\+\-@]')

def _safe_csv(v):
    s = _cell(v)  # reutiliza _cell para convertir dict/list -> JSON string
    return "'" + s if _CSV_INJECTION.match(s) else s

@login_required
def alarms_export_csv(request):
    """
    GET /dashboard/alarms/export.csv
       Parámetros (mismos que la tabla):
         ?days=7&status=open&page_size=200&pages=3&q=texto
         o ?from=2025-10-01&to=2025-10-15
    Exporta TODAS las columnas detectadas en la muestra paginada.
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

        cols = sorted({k for a in alarms for k in a.keys()})
        buff = io.StringIO()
        buff.write("\ufeff")  # BOM UTF-8 para Excel
        w = csv.writer(buff)
        w.writerow(cols)
        for a in alarms:
            w.writerow([_safe_csv(a.get(c)) for c in cols])

        resp = HttpResponse(buff.getvalue(), content_type="text/csv; charset=utf-8")
        resp["Content-Disposition"] = 'attachment; filename="alarms_export.csv"'
        return resp
    except Exception as e:
        return HttpResponseBadRequest(f"Error AlarmsOne: {e}")
