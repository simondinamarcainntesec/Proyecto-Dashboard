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
    # === NUEVO ===
    build_msg_severity_bar_data,
    build_trend_by_msg_severity,
)

# Zona horaria del dashboard (de cara al usuario)
CL_TZ = pytz.timezone("America/Santiago")


# -----------------------------
# Parsers de fecha robustos
# -----------------------------
def _local_start_of_day(date_obj):
    """Inicio local del día -> UTC aware."""
    local_dt = CL_TZ.localize(datetime(date_obj.year, date_obj.month, date_obj.day, 0, 0, 0))
    return local_dt.astimezone(timezone.utc)


def _parse_date_flexible_local_start(s: str):
    """
    Acepta 'YYYY-MM-DD', 'DD-MM-YYYY', 'YYYY/MM/DD', 'DD/MM/YYYY'.
    Devuelve el INICIO local del día en UTC (aware). Si falla, None.
    """
    if not s:
        return None

    s = s.strip()
    # Si viene “2025-10-19T…” (algún browser), córtalo a la parte de fecha.
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


# -----------------------------
# View
# -----------------------------
def dashboard_view(request):
    """
    Render principal. Filtros GET (?from=YYYY-MM-DD&to=YYYY-MM-DD).
    - 'from' => inicio local del día (inclusive)
    - 'to'   => inicio local del día siguiente (exclusivo)
    Si 'from' y 'to' son el MISMO día, el rango incluye ese día completo.
    Acepta tanto YYYY-MM-DD como DD-MM-YYYY (y con '/').
    """
    now_utc = datetime.now(timezone.utc)

    raw_from = (request.GET.get("from") or "").strip()
    raw_to   = (request.GET.get("to") or "").strip()

    parsed_from = _parse_date_flexible_local_start(raw_from)
    parsed_to   = _parse_date_flexible_local_start(raw_to)

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

    # >>> Cambia aquí: build_device_bar_data ahora retorna 3 valores (incluye FULL)
    device_counts, device_by_sev, device_by_sev_full = build_device_bar_data(
    dt_from_utc, dt_to_utc_exclusive, top_n=10
   )


    action_counts, action_by_sev, action_by_device = build_action_bar_data(
        dt_from_utc, dt_to_utc_exclusive, top_n=10
    )
    device_by_action = build_device_by_action(dt_from_utc, dt_to_utc_exclusive, top_n=10)
    kpis = build_kpis(dt_from_utc, dt_to_utc_exclusive)

    hour_payload = build_hour_filter_payload(dt_from_utc, dt_to_utc_exclusive, top_n=10)

    # === NUEVO: msg_severity ===
    (
        msg_severity_counts,
        device_counts_by_msg_severity,
        action_counts_by_msg_severity,
        severity_counts_by_msg_severity,
        msg_severity_counts_by_hour,
    ) = build_msg_severity_bar_data(dt_from_utc, dt_to_utc_exclusive, top_n=10)

    trend_msgsev = build_trend_by_msg_severity(dt_from_utc, dt_to_utc_exclusive)

    # Fechas visibles en el selector:
    def utc_to_local_date_str(dt_utc):
        return dt_utc.astimezone(CL_TZ).date().isoformat()

    if raw_from and parsed_from:
        from_date_str = raw_from
    else:
        from_date_str = utc_to_local_date_str(dt_from_utc)

    if raw_to and parsed_to:
        to_date_str = raw_to
    else:
        to_date_str = utc_to_local_date_str(dt_to_utc_exclusive - timedelta(days=1))

    context = {
        # Trend (por severidad)
        "trend_labels": trend["trend_labels"],
        "trend_data": trend["trend_data"],
        "severity_trends": trend["severity_trends"],

        # Trend por dispositivo
        "trend_by_device": trend_dev["trend_by_device"],
        "top_devices": trend_dev["top_devices"],

        # Trend por acción
        "trend_by_action": trend_act["trend_by_action"],

        # Conteos
        "severity_counts": severity_counts,
        "device_counts": device_counts,
        "action_counts": action_counts,

        # Por severidad (cross-filter front)
        "device_counts_by_severity": device_by_sev,
        "device_counts_by_severity_full": device_by_sev_full,# NEW
        "action_counts_by_severity": action_by_sev,

        # Por acción (cross-filter front)
        "device_counts_by_action": device_by_action,

        # Acciones por dispositivo (para filtrar el bar al click en la tabla)
        "action_counts_by_device": action_by_device,

        # KPIs
        "kpi_total": kpis["kpi_total"],
        "kpi_high": kpis["kpi_high"],
        "kpi_dispositivos": kpis["kpi_dispositivos"],

        # Fechas mostradas en el picker
        "from_date_str": from_date_str,
        "to_date_str": to_date_str,

        # Payload por hora (rango general)
        "hour_labels": hour_payload["hour_labels"],
        "hour_data": hour_payload["hour_data"],
        "severity_counts_by_hour": hour_payload["severity_counts_by_hour"],
        "device_counts_by_hour": hour_payload["device_counts_by_hour"],
        "device_counts_by_hour_full": hour_payload["device_counts_by_hour_full"],  # NEW
        "action_counts_by_hour": hour_payload["action_counts_by_hour"],
        "trend_labels_hour": hour_payload["trend_labels_hour"],
        "trend_by_hour": hour_payload["trend_by_hour"],

        # === NUEVO: msg_severity al contexto ===
        "msg_severity_counts": msg_severity_counts,
        "device_counts_by_msg_severity": device_counts_by_msg_severity,
        "action_counts_by_msg_severity": action_counts_by_msg_severity,
        "severity_counts_by_msg_severity": severity_counts_by_msg_severity,
        "msg_severity_counts_by_hour": msg_severity_counts_by_hour,
        "trend_by_msg_severity": trend_msgsev["trend_by_msg_severity"],
    }
    return render(request, "dashboard/dashboard.html", context)
