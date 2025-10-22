from datetime import datetime, timedelta, timezone
import pytz
from django.shortcuts import render

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
    # === NUEVO ===
    build_level_bar_data,
    build_subtype_bar_data,
    build_log_description_bar_data,
    # === NUEVO (faltantes para que filtre por level) ===
    build_trend_by_level,
    build_level_counts_by_hour,
    build_subtype_counts_by_level,
    build_trend_by_subtype,
    build_subtype_counts_by_hour,
    build_trend_by_subtype,          # si aún no lo importaste
    build_subtype_counts_by_hour,    # si aún no lo importaste
    build_level_counts_by_subtype, 
)

# Zona horaria del dashboard (de cara al usuario)
CL_TZ = pytz.timezone("America/Santiago")


def _local_start_of_day(date_obj):
    """Inicio local del día -> UTC aware."""
    local_dt = CL_TZ.localize(datetime(date_obj.year, date_obj.month, date_obj.day, 0, 0, 0))
    return local_dt.astimezone(timezone.utc)


def _parse_date_flexible_local_start(s: str):
    """Acepta 'YYYY-MM-DD', 'DD-MM-YYYY', 'YYYY/MM/DD', 'DD/MM/YYYY'."""
    if not s:
        return None
    s = s.strip()
    if "T" in s:
        s = s.split("T", 1)[0]
    fmts = ["%Y-%m-%d", "%d-%m-%Y", "%Y/%m/%d", "%d/%m/%Y"]
    for fmt in fmts:
        try:
            d = datetime.strptime(s, fmt).date()
            return _local_start_of_day(d)
        except Exception:
            pass
    return None


def dashboard_view(request):
    """Render principal del dashboard con filtros GET."""
    now_utc = datetime.now(timezone.utc)

    raw_from = (request.GET.get("from") or "").strip()
    raw_to = (request.GET.get("to") or "").strip()

    parsed_from = _parse_date_flexible_local_start(raw_from)
    parsed_to = _parse_date_flexible_local_start(raw_to)

    if raw_from or raw_to:
        if parsed_from and parsed_to:
            dt_from_utc = parsed_from
            dt_to_utc_exclusive = parsed_to + timedelta(days=1)
        elif parsed_from and not parsed_to:
            dt_from_utc = parsed_from
            dt_to_utc_exclusive = now_utc
        elif parsed_to and not parsed_from:
            dt_to_utc_exclusive = parsed_to + timedelta(days=1)
            dt_from_utc = dt_to_utc_exclusive - timedelta(days=30)
        else:
            dt_to_utc_exclusive = now_utc
            dt_from_utc = now_utc - timedelta(days=30)
    else:
        dt_to_utc_exclusive = now_utc
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

    device_counts, device_by_sev, device_by_sev_full = build_device_bar_data(
        dt_from_utc, dt_to_utc_exclusive, top_n=10
    )
    action_counts, action_by_sev, action_by_device = build_action_bar_data(
        dt_from_utc, dt_to_utc_exclusive, top_n=10
    )
    device_by_action = build_device_by_action(dt_from_utc, dt_to_utc_exclusive, top_n=10)
    kpis = build_kpis(dt_from_utc, dt_to_utc_exclusive)
    hour_payload = build_hour_filter_payload(dt_from_utc, dt_to_utc_exclusive, top_n=10)

    # === msg_severity ===
    (
        msg_severity_counts,
        device_counts_by_msg_severity,
        action_counts_by_msg_severity,
        severity_counts_by_msg_severity,
        msg_severity_counts_by_hour,
    ) = build_msg_severity_bar_data(dt_from_utc, dt_to_utc_exclusive, top_n=10)

    trend_msgsev = build_trend_by_msg_severity(dt_from_utc, dt_to_utc_exclusive)

    # === BARRAS por level y subtype ===
    (
        level_counts,
        device_counts_by_level,
        action_counts_by_level,
        severity_counts_by_level,
    ) = build_level_bar_data(dt_from_utc, dt_to_utc_exclusive, top_n=10)

    (
        subtype_counts,
        device_counts_by_subtype,
        action_counts_by_subtype,
        severity_counts_by_subtype,
    ) = build_subtype_bar_data(dt_from_utc, dt_to_utc_exclusive, top_n=10)

    (
        logdesc_counts,
        device_counts_by_logdesc,
        action_counts_by_logdesc,
        severity_counts_by_logdesc,
    ) = build_log_description_bar_data(dt_from_utc, dt_to_utc_exclusive, top_n=10)

    # === NUEVO: datasets que faltaban para cruzar por LEVEL ===
    trend_level = build_trend_by_level(dt_from_utc, dt_to_utc_exclusive)
    level_by_hour = build_level_counts_by_hour(dt_from_utc, dt_to_utc_exclusive)
    subtype_by_level = build_subtype_counts_by_level(dt_from_utc, dt_to_utc_exclusive)
        # Trend por Subtype
    trend_st = build_trend_by_subtype(dt_from_utc, dt_to_utc_exclusive)
    # Hourly por Subtype
    subtype_counts_by_hour = build_subtype_counts_by_hour(dt_from_utc, dt_to_utc_exclusive)
    trend_st = build_trend_by_subtype(dt_from_utc, dt_to_utc_exclusive)

    # Hourly por Subtype
    subtype_counts_by_hour = build_subtype_counts_by_hour(dt_from_utc, dt_to_utc_exclusive)

    # Level por Subtype (NUEVO)
    level_counts_by_subtype = build_level_counts_by_subtype(
        dt_from_utc, dt_to_utc_exclusive, top_n=None  # o un entero para recortar
    )


    def utc_to_local_date_str(dt_utc):
        return dt_utc.astimezone(CL_TZ).date().isoformat()

    from_date_str = raw_from or utc_to_local_date_str(dt_from_utc)
    to_date_str = raw_to or utc_to_local_date_str(dt_to_utc_exclusive - timedelta(days=1))

    context = {
        # Trend base
        "trend_labels": trend["trend_labels"],
        "trend_data": trend["trend_data"],
        "severity_trends": trend["severity_trends"],

        # Trends by category
        "trend_by_device": trend_dev["trend_by_device"],
        "top_devices": trend_dev["top_devices"],
        "trend_by_action": trend_act["trend_by_action"],
        # NUEVO: trend por level
        "trend_by_level": trend_level["trend_by_level"],

        # Counts
        "severity_counts": severity_counts,
        "device_counts": device_counts,
        "action_counts": action_counts,

        # Cross-filter
        "device_counts_by_severity": device_by_sev,
        "device_counts_by_severity_full": device_by_sev_full,
        "action_counts_by_severity": action_by_sev,
        "device_counts_by_action": device_by_action,
        "action_counts_by_device": action_by_device,

        # KPIs
        "kpi_total": kpis["kpi_total"],
        "kpi_high": kpis["kpi_high"],
        "kpi_dispositivos": kpis["kpi_dispositivos"],

        # Fecha visible
        "from_date_str": from_date_str,
        "to_date_str": to_date_str,

        # Por hora
        "hour_labels": hour_payload["hour_labels"],
        "hour_data": hour_payload["hour_data"],
        "severity_counts_by_hour": hour_payload["severity_counts_by_hour"],
        "device_counts_by_hour": hour_payload["device_counts_by_hour"],
        "device_counts_by_hour_full": hour_payload["device_counts_by_hour_full"],
        "action_counts_by_hour": hour_payload["action_counts_by_hour"],
        "trend_labels_hour": hour_payload["trend_labels_hour"],
        "trend_by_hour": hour_payload["trend_by_hour"],
        # NUEVO: por hour x level
        "level_counts_by_hour": level_by_hour["level_counts_by_hour"],

        # msg_severity
        "msg_severity_counts": msg_severity_counts,
        "device_counts_by_msg_severity": device_counts_by_msg_severity,
        "action_counts_by_msg_severity": action_counts_by_msg_severity,
        "severity_counts_by_msg_severity": severity_counts_by_msg_severity,
        "msg_severity_counts_by_hour": msg_severity_counts_by_hour,
        "trend_by_msg_severity": trend_msgsev["trend_by_msg_severity"],

        # Level/Subtype
        "level_counts": level_counts,
        "device_counts_by_level": device_counts_by_level,
        "action_counts_by_level": action_counts_by_level,
        "severity_counts_by_level": severity_counts_by_level,
        # NUEVO: subtype por level
        "subtype_counts_by_level": subtype_by_level["subtype_counts_by_level"],

        # Subtype base
        "subtype_counts": subtype_counts,
        "device_counts_by_subtype": device_counts_by_subtype,
        "action_counts_by_subtype": action_counts_by_subtype,
        "severity_counts_by_subtype": severity_counts_by_subtype,

        # Log description
        "logdesc_counts": logdesc_counts,
        "device_counts_by_logdesc": device_counts_by_logdesc,
        "action_counts_by_logdesc": action_counts_by_logdesc,
        "severity_counts_by_logdesc": severity_counts_by_logdesc,
                # Trend por Subtype
        "trend_by_subtype": trend_st["trend_by_subtype"],
        # Hourly por Subtype
        "subtype_counts_by_hour": subtype_counts_by_hour,
        "trend_by_subtype": trend_st["trend_by_subtype"],
        "subtype_counts_by_hour": subtype_counts_by_hour,
        "level_counts_by_subtype": level_counts_by_subtype,


    }

    return render(request, "dashboard/dashboard.html", context)
