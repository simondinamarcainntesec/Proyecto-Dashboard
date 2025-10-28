from datetime import datetime, timedelta, timezone
import logging
import pytz

from django.shortcuts import render
from django.views.decorators.cache import never_cache
from tenants.decorators import tenant_required

from .charts import (
    build_trend_data,
    build_trend_by_device,
    build_donut_data,
    build_device_bar_data,
    build_action_bar_data,
    build_kpis,
    build_trend_by_action,
    build_device_by_action,
    build_hour_filter_payload,
    build_msg_severity_bar_data,
    build_trend_by_msg_severity,
    build_level_bar_data,
    build_subtype_bar_data,
    build_log_description_bar_data,
    build_trend_by_level,
    build_level_counts_by_hour,
    build_subtype_counts_by_level,
    build_trend_by_subtype,
    build_subtype_counts_by_hour,
    build_level_counts_by_subtype,
    build_msg_severity_by_level,
    build_msg_severity_by_subtype,
    build_level_by_msg_severity,
    build_subtype_by_msg_severity,
    build_hour_series_by_subtype,
)

logger = logging.getLogger(__name__)
CL_TZ = pytz.timezone("America/Santiago")

# -----------------------------
# Helpers de fecha
# -----------------------------
def _localize_naive(dt_naive):
    """Recibe datetime naive en hora local CL y lo vuelve aware en UTC."""
    return CL_TZ.localize(dt_naive).astimezone(timezone.utc)

def _parse_local_any(s: str):
    """
    Devuelve (dt_utc, tipo) donde tipo ∈ {"date","datetime"}.
    Acepta:
      - 'YYYY-MM-DD' | 'DD-MM-YYYY' | 'YYYY/MM/DD' | 'DD/MM/YYYY'
      - 'YYYY-MM-DDTHH:MM:SS' | 'YYYY-MM-DD HH:MM:SS'
    """
    if not s:
        return None, None
    s = s.strip()

    # datetime
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            dt_local = datetime.strptime(s, fmt)
            return _localize_naive(dt_local), "datetime"
        except Exception:
            pass

    # date
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%Y/%m/%d", "%d/%m/%Y"):
        try:
            d = datetime.strptime(s, fmt).date()
            start_local = datetime(d.year, d.month, d.day, 0, 0, 0)
            return _localize_naive(start_local), "date"
        except Exception:
            pass

    return None, None

# ===========================
# ÚNICA vista del dashboard
# ===========================
@never_cache
@tenant_required
def dashboard_view(request):
    tenant = request.tenant  # <- importante para el cache por-tenant en el template

    now_utc = datetime.now(timezone.utc)
    raw_from = (request.GET.get("from") or "").strip()
    raw_to   = (request.GET.get("to") or "").strip()

    parsed_from_utc, kind_from = _parse_local_any(raw_from)
    parsed_to_utc,   kind_to   = _parse_local_any(raw_to)

    # Rango final [from, to)
    if raw_from or raw_to:
        if parsed_from_utc and parsed_to_utc:
            dt_from_utc = parsed_from_utc
            dt_to_utc_exclusive = parsed_to_utc + (timedelta(seconds=1) if kind_to == "datetime" else timedelta(days=1))
        elif parsed_from_utc and not parsed_to_utc:
            dt_from_utc = parsed_from_utc
            dt_to_utc_exclusive = now_utc + timedelta(seconds=1)
        elif parsed_to_utc and not parsed_from_utc:
            dt_to_utc_exclusive = parsed_to_utc + (timedelta(seconds=1) if kind_to == "datetime" else timedelta(days=1))
            dt_from_utc = dt_to_utc_exclusive - timedelta(days=30)
        else:
            dt_to_utc_exclusive = now_utc + timedelta(seconds=1)
            dt_from_utc = now_utc - timedelta(days=30)
    else:
        dt_to_utc_exclusive = now_utc + timedelta(seconds=1)
        dt_from_utc = now_utc - timedelta(days=30)

    if dt_from_utc >= dt_to_utc_exclusive:
        dt_to_utc_exclusive = dt_from_utc + timedelta(days=1)

    # ===========================
    # Construcción de datasets
    # ===========================
    trend = build_trend_data(dt_from_utc, dt_to_utc_exclusive)
    trend_dev = build_trend_by_device(dt_from_utc, dt_to_utc_exclusive, top_n=10)
    trend_act = build_trend_by_action(dt_from_utc, dt_to_utc_exclusive)
    severity_counts = build_donut_data(dt_from_utc, dt_to_utc_exclusive)

    device_counts, device_by_sev, device_by_sev_full = build_device_bar_data(dt_from_utc, dt_to_utc_exclusive, top_n=10)
    action_counts, action_by_sev, action_by_device = build_action_bar_data(dt_from_utc, dt_to_utc_exclusive, top_n=10)
    device_by_action = build_device_by_action(dt_from_utc, dt_to_utc_exclusive, top_n=10)
    kpis = build_kpis(dt_from_utc, dt_to_utc_exclusive)
    hour_payload = build_hour_filter_payload(dt_from_utc, dt_to_utc_exclusive, top_n=10)

    # msg_severity
    (msg_severity_counts,
     device_counts_by_msg_severity,
     action_counts_by_msg_severity,
     severity_counts_by_msg_severity,
     msg_severity_counts_by_hour) = build_msg_severity_bar_data(dt_from_utc, dt_to_utc_exclusive, top_n=10)
    trend_msgsev = build_trend_by_msg_severity(dt_from_utc, dt_to_utc_exclusive)

    # level / subtype / logdesc
    (level_counts,
     device_counts_by_level,
     action_counts_by_level,
     severity_counts_by_level) = build_level_bar_data(dt_from_utc, dt_to_utc_exclusive, top_n=10)

    (subtype_counts,
     device_counts_by_subtype,
     action_counts_by_subtype,
     severity_counts_by_subtype) = build_subtype_bar_data(dt_from_utc, dt_to_utc_exclusive, top_n=10)

    (logdesc_counts,
     device_counts_by_logdesc,
     action_counts_by_logdesc,
     severity_counts_by_logdesc) = build_log_description_bar_data(dt_from_utc, dt_to_utc_exclusive, top_n=10)

    msgsev_by_level   = build_msg_severity_by_level(dt_from_utc, dt_to_utc_exclusive)
    msgsev_by_subtype = build_msg_severity_by_subtype(dt_from_utc, dt_to_utc_exclusive)

    trend_level   = build_trend_by_level(dt_from_utc, dt_to_utc_exclusive)
    level_by_hour = build_level_counts_by_hour(dt_from_utc, dt_to_utc_exclusive)
    subtype_by_level = build_subtype_counts_by_level(dt_from_utc, dt_to_utc_exclusive)

    trend_st = build_trend_by_subtype(dt_from_utc, dt_to_utc_exclusive)
    subtype_counts_by_hour = build_subtype_counts_by_hour(dt_from_utc, dt_to_utc_exclusive)

    level_counts_by_subtype = build_level_counts_by_subtype(dt_from_utc, dt_to_utc_exclusive, top_n=None)
    level_by_msgsev   = build_level_by_msg_severity(dt_from_utc, dt_to_utc_exclusive)
    subtype_by_msgsev = build_subtype_by_msg_severity(dt_from_utc, dt_to_utc_exclusive)
    hour_series_by_subtype = build_hour_series_by_subtype(dt_from_utc, dt_to_utc_exclusive)

    def utc_to_local_date_str(dt_utc):
        return dt_utc.astimezone(CL_TZ).date().isoformat()

    from_date_str = raw_from or utc_to_local_date_str(dt_from_utc)
    to_date_str   = raw_to   or utc_to_local_date_str(dt_to_utc_exclusive)

    context = {
        # clave para cache fragmentado por tenant en el template
        "tenant": tenant,

        "trend_labels": trend["trend_labels"],
        "trend_data": trend["trend_data"],
        "severity_trends": trend["severity_trends"],

        "trend_by_device": trend_dev["trend_by_device"],
        "top_devices": trend_dev["top_devices"],
        "trend_by_action": trend_act["trend_by_action"],
        "trend_by_level": trend_level["trend_by_level"],

        "severity_counts": severity_counts,
        "device_counts": device_counts,
        "action_counts": action_counts,

        "device_counts_by_severity": device_by_sev,
        "device_counts_by_severity_full": device_by_sev_full,
        "action_counts_by_severity": action_by_sev,
        "device_counts_by_action": device_by_action,
        "action_counts_by_device": action_by_device,

        "kpi_total": kpis["kpi_total"],
        "kpi_high": kpis["kpi_high"],
        "kpi_dispositivos": kpis["kpi_dispositivos"],

        "from_date_str": from_date_str,
        "to_date_str": to_date_str,

        "hour_labels": hour_payload["hour_labels"],
        "hour_data": hour_payload["hour_data"],
        "severity_counts_by_hour": hour_payload["severity_counts_by_hour"],
        "device_counts_by_hour": hour_payload["device_counts_by_hour"],
        "device_counts_by_hour_full": hour_payload["device_counts_by_hour_full"],
        "action_counts_by_hour": hour_payload["action_counts_by_hour"],
        "trend_labels_hour": hour_payload["trend_labels_hour"],
        "trend_by_hour": hour_payload["trend_by_hour"],
        "level_counts_by_hour": level_by_hour["level_counts_by_hour"],

        "msg_severity_counts": msg_severity_counts,
        "device_counts_by_msg_severity": device_counts_by_msg_severity,
        "action_counts_by_msg_severity": action_counts_by_msg_severity,
        "severity_counts_by_msg_severity": severity_counts_by_msg_severity,
        "msg_severity_counts_by_hour": msg_severity_counts_by_hour,
        "trend_by_msg_severity": trend_msgsev["trend_by_msg_severity"],

        "level_counts": level_counts,
        "device_counts_by_level": device_counts_by_level,
        "action_counts_by_level": action_counts_by_level,
        "severity_counts_by_level": severity_counts_by_level,
        "subtype_counts_by_level": subtype_by_level["subtype_counts_by_level"],

        "subtype_counts": subtype_counts,
        "device_counts_by_subtype": device_counts_by_subtype,
        "action_counts_by_subtype": action_counts_by_subtype,
        "severity_counts_by_subtype": severity_counts_by_subtype,
        "trend_by_subtype": trend_st["trend_by_subtype"],
        "subtype_counts_by_hour": subtype_counts_by_hour,

        "logdesc_counts": logdesc_counts,
        "device_counts_by_logdesc": device_counts_by_logdesc,
        "action_counts_by_logdesc": action_counts_by_logdesc,
        "severity_counts_by_logdesc": severity_counts_by_logdesc,

        "level_counts_by_subtype": level_counts_by_subtype,
        "msg_severity_by_level": msgsev_by_level["msg_severity_by_level"],
        "msg_severity_by_subtype": msgsev_by_subtype["msg_severity_by_subtype"],
        "level_by_msg_severity": level_by_msgsev["level_by_msg_severity"],
        "subtype_by_msg_severity": subtype_by_msgsev["subtype_by_msg_severity"],
        "hour_series_by_subtype": hour_series_by_subtype["hour_series_by_subtype"],
    }

    resp = render(request, "dashboard/dashboard.html", context)
    # headers anti-caché para el documento HTML
    resp["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    resp["Pragma"] = "no-cache"
    resp["Expires"] = "0"
    resp["Vary"] = "Cookie"
    return resp
