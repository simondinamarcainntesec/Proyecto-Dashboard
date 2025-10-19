# mysite/dashboard/views.py
from datetime import datetime, timedelta, timezone
from django.shortcuts import render

from .charts import (
    build_trend_data,
    build_trend_by_device,
    build_donut_data,
    build_device_bar_data,
    build_action_bar_data,
    build_kpis,
    build_trend_by_action,      # <-- nuevo
    build_device_by_action,     # <-- nuevo
)

def _parse_date_yyyy_mm_dd(s: str):
    if not s:
        return None
    try:
        dt = datetime.strptime(s.strip(), "%Y-%m-%d")
        return dt.replace(tzinfo=timezone.utc)
    except Exception:
        return None

def dashboard_view(request):
    """
    Render principal. Filtros GET:
      ?from=YYYY-MM-DD&to=YYYY-MM-DD
      (si no vienen, usa últimos 30 días)
    """
    now = datetime.now(timezone.utc)
    dt_from = _parse_date_yyyy_mm_dd(request.GET.get("from")) or (now - timedelta(days=30))
    dt_to   = _parse_date_yyyy_mm_dd(request.GET.get("to"))   or now

    # Series temporales
    trend = build_trend_data(dt_from, dt_to)
    trend_dev = build_trend_by_device(dt_from, dt_to, top_n=10)
    trend_act = build_trend_by_action(dt_from, dt_to)  # <-- nuevo

    # Donut + Barras + KPIs
    severity_counts = build_donut_data(dt_from, dt_to)
    device_counts, device_by_sev = build_device_bar_data(dt_from, dt_to, top_n=10)
    action_counts, action_by_sev = build_action_bar_data(dt_from, dt_to, top_n=10)
    device_by_action = build_device_by_action(dt_from, dt_to, top_n=10)  # <-- nuevo
    kpis = build_kpis(dt_from, dt_to)

    context = {
        # Trend (por severidad)
        "trend_labels": trend["trend_labels"],
        "trend_data": trend["trend_data"],
        "severity_trends": trend["severity_trends"],

        # Trend por dispositivo
        "trend_by_device": trend_dev["trend_by_device"],
        "top_devices": trend_dev["top_devices"],

        # NUEVO: Trend por acción
        "trend_by_action": trend_act["trend_by_action"],

        # Conteos
        "severity_counts": severity_counts,
        "device_counts": device_counts,
        "action_counts": action_counts,

        # Por severidad (para cross-filter en front)
        "device_counts_by_severity": device_by_sev,
        "action_counts_by_severity": action_by_sev,

        # NUEVO: Por acción (para cross-filter en front)
        "device_counts_by_action": device_by_action,

        # KPIs
        "kpi_total": kpis["kpi_total"],
        "kpi_high": kpis["kpi_high"],
        "kpi_dispositivos": kpis["kpi_dispositivos"],

        # Para pre-llenar el selector de fechas
        "from_date_str": (dt_from.astimezone(timezone.utc)).date().isoformat(),
        "to_date_str": (dt_to.astimezone(timezone.utc)).date().isoformat(),
    }
    return render(request, "dashboard/dashboard.html", context)
