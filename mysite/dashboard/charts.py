import logging
from collections import defaultdict, Counter
from datetime import timedelta
import pytz

from django.db.models import Count
from django.db.models.functions import TruncDay, TruncHour

from inyeccion_api.models import Alarm  # Importar model de alarmas

logger = logging.getLogger(__name__)

# TZ local para el dashboard
CL_TZ = pytz.timezone("America/Santiago")


def _base_qs(dt_from=None, dt_to=None):
    qs = Alarm.objects.all()
    if dt_from and dt_to:
        qs = qs.filter(event_time__range=(dt_from, dt_to))
    return qs


def build_trend_data(dt_from=None, dt_to=None):
    """
    Eje temporal (por día) y series por severidad.
    """
    qs = _base_qs(dt_from, dt_to)

    daily = (
        qs.annotate(date=TruncDay("event_time"))
          .values("date")
          .annotate(total=Count("id"))
          .order_by("date")
    )
    trend_labels = [d["date"].strftime("%Y-%m-%d") for d in daily]
    trend_data = [d["total"] for d in daily]

    severity_qs = (
        qs.annotate(date=TruncDay("event_time"))
          .values("date", "severity")
          .annotate(total=Count("id"))
          .order_by("date")
    )
    severities = list(qs.values_list("severity", flat=True).distinct())
    severities = [s if s is not None else "N/A" for s in severities]

    severity_trends = {s: {"data": [0] * len(trend_labels)} for s in severities}
    idx = {d: i for i, d in enumerate(trend_labels)}

    for row in severity_qs:
        date_str = row["date"].strftime("%Y-%m-%d")
        sev = row["severity"] if row["severity"] is not None else "N/A"
        i = idx.get(date_str)
        if i is not None:
            severity_trends[sev]["data"][i] = row["total"]

    return {
        "trend_labels": trend_labels,
        "trend_data": trend_data,
        "severity_trends": severity_trends,
    }


def build_trend_by_device(dt_from=None, dt_to=None, top_n=10):
    """
    Series por día para los TOP N dispositivos (todas las severidades).
    """
    qs = _base_qs(dt_from, dt_to)

    top = list(
        qs.values("device_name")
          .annotate(total=Count("id"))
          .order_by("-total")[:top_n]
    )
    top_devices = [r["device_name"] or "N/A" for r in top]

    daily = (
        qs.annotate(date=TruncDay("event_time"))
          .values("date")
          .annotate(total=Count("id"))
          .order_by("date")
    )
    labels = [d["date"].strftime("%Y-%m-%d") for d in daily]
    idx = {d: i for i, d in enumerate(labels)}

    device_rows = (
        qs.filter(device_name__in=top_devices)
          .annotate(date=TruncDay("event_time"))
          .values("date", "device_name")
          .annotate(total=Count("id"))
          .order_by("date")
    )
    trend_by_device = {dev: [0] * len(labels) for dev in top_devices}
    for r in device_rows:
        date_str = r["date"].strftime("%Y-%m-%d")
        dev = r["device_name"] or "N/A"
        i = idx.get(date_str)
        if i is not None:
            trend_by_device[dev][i] = r["total"]

    return {"trend_by_device": trend_by_device, "top_devices": top_devices}


def build_trend_by_action(dt_from=None, dt_to=None):
    """
    Series por día para cada acción (Open/Blocked/Resolved, etc).
    """
    qs = _base_qs(dt_from, dt_to)

    # Eje temporal base
    daily = (
        qs.annotate(date=TruncDay("event_time"))
          .values("date")
          .annotate(total=Count("id"))
          .order_by("date")
    )
    labels = [d["date"].strftime("%Y-%m-%d") for d in daily]
    idx = {d: i for i, d in enumerate(labels)}

    rows = (
        qs.annotate(date=TruncDay("event_time"))
          .values("date", "actions")   # <<<<< CAMBIO
          .annotate(total=Count("id"))
          .order_by("date")
    )

    trend_by_action = defaultdict(lambda: [0]*len(labels))
    for r in rows:
        date_str = r["date"].strftime("%Y-%m-%d")
        act = r["actions"] or "N/A"    # <<<<< CAMBIO
        i = idx.get(date_str)
        if i is not None:
            trend_by_action[act][i] = r["total"]

    return {"trend_by_action": dict(trend_by_action), "trend_labels": labels}


def build_donut_data(dt_from=None, dt_to=None):
    """
    Dict {severity: total}
    """
    qs = _base_qs(dt_from, dt_to)
    raw = qs.values("severity").annotate(total=Count("id")).order_by("severity")
    return {(r["severity"] if r["severity"] is not None else "N/A"): r["total"] for r in raw}


def build_device_bar_data(dt_from=None, dt_to=None, top_n=10):
    """
    (global, por_severidad) para tabla y cross-filter.
    Además devuelve el mapa COMPLETO severidad->device (sin top_n)
    para que el front pueda filtrar correctamente el donut.
    """
    qs = _base_qs(dt_from, dt_to)

    rows = qs.values("device_name").annotate(total=Count("id")).order_by("-total")[:top_n]
    device_counts = {(r["device_name"] or "N/A"): r["total"] for r in rows}

    by_sev = defaultdict(Counter)
    for r in qs.values("severity", "device_name").annotate(total=Count("id")):
        sev = r["severity"] if r["severity"] is not None else "N/A"
        dev = r["device_name"] or "N/A"
        by_sev[sev][dev] = r["total"]

    # full (sin recortar)
    device_counts_by_severity_full = {sev: dict(cnt) for sev, cnt in by_sev.items()}

    # recortado a top_n (como tenías)
    device_counts_by_severity = {
        sev: dict(sorted(cnt.items(), key=lambda x: x[1], reverse=True)[:top_n])
        for sev, cnt in by_sev.items()
    }
    # ⬅️ AHORA devolvemos 3 valores
    return device_counts, device_counts_by_severity, device_counts_by_severity_full



def build_action_bar_data(dt_from=None, dt_to=None, top_n=10):
    """
    (global, por_severidad) para barra Acciones y cross-filter.
    """
    qs = _base_qs(dt_from, dt_to)

    rows = qs.values("actions").annotate(total=Count("id")).order_by("-total")[:top_n]  # <<<<< CAMBIO
    action_counts = {(r["actions"] or "N/A"): r["total"] for r in rows}                # <<<<< CAMBIO

    by_sev = defaultdict(Counter)
    for r in qs.values("severity", "actions").annotate(total=Count("id")):             # <<<<< CAMBIO
        sev = r["severity"] if r["severity"] is not None else "N/A"
        act = r["actions"] or "N/A"                                                    # <<<<< CAMBIO
        by_sev[sev][act] = r["total"]

    action_counts_by_severity = {
        sev: dict(sorted(cnt.items(), key=lambda x: x[1], reverse=True)[:top_n])
        for sev, cnt in by_sev.items()
    }

    # NUEVO: acciones por dispositivo (para filtrar el bar de acciones al click en la tabla)
    by_dev = defaultdict(Counter)
    for r in _base_qs(dt_from, dt_to).values("device_name", "actions").annotate(total=Count("id")):  # <<<<< CAMBIO
        dev = r["device_name"] or "N/A"
        act = r["actions"] or "N/A"                                                                  # <<<<< CAMBIO
        by_dev[dev][act] = r["total"]
    action_counts_by_device = {dev: dict(cnt) for dev, cnt in by_dev.items()}

    return action_counts, action_counts_by_severity, action_counts_by_device


def build_device_by_action(dt_from=None, dt_to=None, top_n=10):
    """
    Ranking de dispositivos por acción: { 'Open': {'DevA': n, ...}, 'Blocked': {...}, ... }
    """
    qs = _base_qs(dt_from, dt_to)

    by_action = defaultdict(Counter)
    rows = (
        qs.values("actions", "device_name")   # <<<<< CAMBIO
          .annotate(total=Count("id"))
          .order_by("-total")
    )
    for r in rows:
        act = r["actions"] or "N/A"          # <<<<< CAMBIO
        dev = r["device_name"] or "N/A"
        by_action[act][dev] = r["total"]

    device_counts_by_action = {
        act: dict(sorted(cnt.items(), key=lambda x: x[1], reverse=True)[:top_n])
        for act, cnt in by_action.items()
    }
    return device_counts_by_action


def build_kpis(dt_from=None, dt_to=None):
    """
    KPIs: total, high/critical y dispositivos únicos.
    """
    qs = _base_qs(dt_from, dt_to)
    total = qs.count()
    high = qs.filter(severity__iexact="high").count() + qs.filter(severity__iexact="critical").count()
    dispositivos = qs.values("device_name").distinct().count()
    return {"kpi_total": total, "kpi_high": high, "kpi_dispositivos": dispositivos}


# === NUEVO: payload para filtro por HORA (usa el rango general from/to) ===
def build_hour_filter_payload(dt_from, dt_to, top_n=10):
    """
    Devuelve:
      - hour_labels, hour_data (histograma 00..23 en TZ local)
      - severity_counts_by_hour: { '00': {sev: n, ...}, ... }
      - device_counts_by_hour:   { '00': {dev: n, ...}, ... } (top_n por hora)
      - device_counts_by_hour_full: { '00': {dev: n, ...}, ... } (FULL sin top_n)
      - action_counts_by_hour:   { '00': {act: n, ...}, ... }
      - trend_by_hour:           { '00': [por día], ... } usando las mismas fechas de trend_labels
    """
    qs = _base_qs(dt_from, dt_to)

    # 1) Histograma por hora local
    hour_rows = (
        qs.annotate(h=TruncHour("event_time", tzinfo=CL_TZ))
          .values("h")
          .annotate(total=Count("id"))
          .order_by("h")
    )
    hour_counts = Counter()
    for r in hour_rows:
        h = r.get("h")
        if h:
            key = h.strftime("%H")  # "00".."23"
            hour_counts[key] += r["total"]
    hour_labels = [f"{i:02d}" for i in range(24)]
    hour_data = [hour_counts.get(lbl, 0) for lbl in hour_labels]

    # 2) Por severidad y hora
    sev_rows = (
        qs.annotate(h=TruncHour("event_time", tzinfo=CL_TZ))
          .values("h", "severity")
          .annotate(total=Count("id"))
    )
    severity_counts_by_hour = defaultdict(lambda: defaultdict(int))
    for r in sev_rows:
        h = r.get("h")
        if h:
            hour = h.strftime("%H")
            sev = r["severity"] if r["severity"] is not None else "N/A"
            severity_counts_by_hour[hour][sev] += r["total"]
    severity_counts_by_hour = {h: dict(m) for h, m in severity_counts_by_hour.items()}

    # 3) Por dispositivo y hora (FULL y luego top_n)
    dev_rows = (
        qs.annotate(h=TruncHour("event_time", tzinfo=CL_TZ))
          .values("h", "device_name")
          .annotate(total=Count("id"))
    )
    device_counts_by_hour_full = defaultdict(lambda: defaultdict(int))
    for r in dev_rows:
        h = r.get("h")
        if h:
            hour = h.strftime("%H")
            dev = r["device_name"] or "N/A"
            device_counts_by_hour_full[hour][dev] += r["total"]
    # versión recortada para UI
    device_counts_by_hour = {
        h: dict(sorted(m.items(), key=lambda x: x[1], reverse=True)[:top_n])
        for h, m in device_counts_by_hour_full.items()
    }
    # FULL sin recorte para filtros por dispositivo
    device_counts_by_hour_full = {h: dict(m) for h, m in device_counts_by_hour_full.items()}

    # 4) Por acción y hora  (usa 'actions')
    act_rows = (
        qs.annotate(h=TruncHour("event_time", tzinfo=CL_TZ))
          .values("h", "actions")     # <<<<< CAMBIO
          .annotate(total=Count("id"))
    )
    action_counts_by_hour = defaultdict(lambda: defaultdict(int))
    for r in act_rows:
        h = r.get("h")
        if h:
            hour = h.strftime("%H")
            act = r["actions"] or "N/A"  # <<<<< CAMBIO
            action_counts_by_hour[hour][act] += r["total"]
    action_counts_by_hour = {h: dict(m) for h, m in action_counts_by_hour.items()}

    # 5) Trend por día + hora
    daily = (
        qs.annotate(date=TruncDay("event_time", tzinfo=CL_TZ), h=TruncHour("event_time", tzinfo=CL_TZ))
          .values("date", "h")
          .annotate(total=Count("id"))
          .order_by("date")
    )
    trend_dates = sorted({r["date"] for r in daily if r.get("date")})
    trend_labels = [d.strftime("%Y-%m-%d") for d in trend_dates]
    idx = {d: i for i, d in enumerate(trend_labels)}
    trend_by_hour = {f"{i:02d}": [0]*len(trend_labels) for i in range(24)}

    for r in daily:
        d = r.get("date")
        h = r.get("h")
        if not d or not h:
            continue
        hour = h.strftime("%H")
        di = idx.get(d.strftime("%Y-%m-%d"))
        if di is not None:
            trend_by_hour[hour][di] += r["total"]

    return {
        "hour_labels": hour_labels,
        "hour_data": hour_data,
        "severity_counts_by_hour": severity_counts_by_hour,
        "device_counts_by_hour": device_counts_by_hour,           # top_n (UI)
        "device_counts_by_hour_full": device_counts_by_hour_full, # NEW (FULL)
        "action_counts_by_hour": action_counts_by_hour,
        "trend_labels_hour": trend_labels,
        "trend_by_hour": trend_by_hour,
    }


# =========================
# === NUEVO: msg_severity
# =========================
def build_msg_severity_bar_data(dt_from=None, dt_to=None, top_n=10):
    """
    Devuelve:
      - msg_severity_counts: { msg_severity: total } (TOP N)
      - device_counts_by_msg_severity: { msgsev: {device: n, ...}, ... }
      - action_counts_by_msg_severity: { msgsev: {action: n, ...}, ... }
      - severity_counts_by_msg_severity: { msgsev: {severity: n, ...}, ... }
      - msg_severity_counts_by_hour: { '00': {msgsev: n, ...}, ... }
    """
    qs = _base_qs(dt_from, dt_to)

    # Global (top N)
    rows = qs.values("msg_severity").annotate(total=Count("id")).order_by("-total")[:top_n]
    msg_severity_counts = {(r["msg_severity"] or "N/A"): r["total"] for r in rows}

    # Por dispositivo
    by_msg_dev = defaultdict(Counter)
    for r in qs.values("msg_severity", "device_name").annotate(total=Count("id")):
        msg = r["msg_severity"] or "N/A"
        dev = r["device_name"] or "N/A"
        by_msg_dev[msg][dev] = r["total"]
    device_counts_by_msg_severity = {msg: dict(cnt) for msg, cnt in by_msg_dev.items()}

    # Por acción  (usa 'actions')
    by_msg_act = defaultdict(Counter)
    for r in qs.values("msg_severity", "actions").annotate(total=Count("id")):  # <<<<< CAMBIO
        msg = r["msg_severity"] or "N/A"
        act = r["actions"] or "N/A"                                            # <<<<< CAMBIO
        by_msg_act[msg][act] = r["total"]
    action_counts_by_msg_severity = {msg: dict(cnt) for msg, cnt in by_msg_act.items()}

    # Por "severity" (para recalcular donut/KPIs cuando se filtre por msg_severity)
    by_msg_sev = defaultdict(Counter)
    for r in qs.values("msg_severity", "severity").annotate(total=Count("id")):
        msg = r["msg_severity"] or "N/A"
        sev = r["severity"] if r["severity"] is not None else "N/A"
        by_msg_sev[msg][sev] = r["total"]
    severity_counts_by_msg_severity = {msg: dict(cnt) for msg, cnt in by_msg_sev.items()}

    # Por hora (para que el gráfico por hora se adapte al filtro msg_severity)
    by_hour_msg = defaultdict(Counter)
    rows_hour = (
        qs.annotate(h=TruncHour("event_time", tzinfo=CL_TZ))
          .values("h", "msg_severity")
          .annotate(total=Count("id"))
    )
    for r in rows_hour:
        h = r.get("h")
        if h:
            hour = h.strftime("%H")
            msg = r["msg_severity"] or "N/A"
            by_hour_msg[hour][msg] += r["total"]
    msg_severity_counts_by_hour = {h: dict(cnt) for h, cnt in by_hour_msg.items()}

    return (
        msg_severity_counts,
        device_counts_by_msg_severity,
        action_counts_by_msg_severity,
        severity_counts_by_msg_severity,
        msg_severity_counts_by_hour,
    )


def build_trend_by_msg_severity(dt_from=None, dt_to=None):
    """
    Series por día para cada msg_severity.
    """
    qs = _base_qs(dt_from, dt_to)

    # Eje temporal base
    daily = (
        qs.annotate(date=TruncDay("event_time"))
          .values("date")
          .annotate(total=Count("id"))
          .order_by("date")
    )
    labels = [d["date"].strftime("%Y-%m-%d") for d in daily]
    idx = {d: i for i, d in enumerate(labels)}

    rows = (
        qs.annotate(date=TruncDay("event_time"))
          .values("date", "msg_severity")
          .annotate(total=Count("id"))
          .order_by("date")
    )

    trend_by_msg_severity = defaultdict(lambda: [0]*len(labels))
    for r in rows:
        date_str = r["date"].strftime("%Y-%m-%d")
        msg = r["msg_severity"] or "N/A"
        i = idx.get(date_str)
        if i is not None:
            trend_by_msg_severity[msg][i] = r["total"]

    return {"trend_by_msg_severity": dict(trend_by_msg_severity), "trend_labels": labels}
def build_level_bar_data(dt_from=None, dt_to=None, top_n=10):
    qs = _base_qs(dt_from, dt_to)

    rows = qs.values("level").annotate(total=Count("id")).order_by("-total")[:top_n]
    level_counts = {(r["level"] or "N/A"): r["total"] for r in rows}

    by_dev = defaultdict(Counter)
    for r in qs.values("level", "device_name").annotate(total=Count("id")):
        lvl = r["level"] or "N/A"
        dev = r["device_name"] or "N/A"
        by_dev[lvl][dev] = r["total"]
    device_counts_by_level = {lvl: dict(cnt) for lvl, cnt in by_dev.items()}

    by_act = defaultdict(Counter)
    for r in qs.values("level", "actions").annotate(total=Count("id")):
        lvl = r["level"] or "N/A"
        act = r["actions"] or "N/A"
        by_act[lvl][act] = r["total"]
    action_counts_by_level = {lvl: dict(cnt) for lvl, cnt in by_act.items()}

    by_sev = defaultdict(Counter)
    for r in qs.values("level", "severity").annotate(total=Count("id")):
        lvl = r["level"] or "N/A"
        sev = r["severity"] if r["severity"] is not None else "N/A"
        by_sev[lvl][sev] = r["total"]
    severity_counts_by_level = {lvl: dict(cnt) for lvl, cnt in by_sev.items()}

    return (
        level_counts,
        device_counts_by_level,
        action_counts_by_level,
        severity_counts_by_level,
    )


# =============================
# === NUEVO: barras SUBTYPE ===
# =============================
def build_subtype_bar_data(dt_from=None, dt_to=None, top_n=10):
    qs = _base_qs(dt_from, dt_to)

    rows = qs.values("subtype").annotate(total=Count("id")).order_by("-total")[:top_n]
    subtype_counts = {(r["subtype"] or "N/A"): r["total"] for r in rows}

    by_dev = defaultdict(Counter)
    for r in qs.values("subtype", "device_name").annotate(total=Count("id")):
        st = r["subtype"] or "N/A"
        dev = r["device_name"] or "N/A"
        by_dev[st][dev] = r["total"]
    device_counts_by_subtype = {st: dict(cnt) for st, cnt in by_dev.items()}

    by_act = defaultdict(Counter)
    for r in qs.values("subtype", "actions").annotate(total=Count("id")):
        st = r["subtype"] or "N/A"
        act = r["actions"] or "N/A"
        by_act[st][act] = r["total"]
    action_counts_by_subtype = {st: dict(cnt) for st, cnt in by_act.items()}

    by_sev = defaultdict(Counter)
    for r in qs.values("subtype", "severity").annotate(total=Count("id")):
        st = r["subtype"] or "N/A"
        sev = r["severity"] if r["severity"] is not None else "N/A"
        by_sev[st][sev] = r["total"]
    severity_counts_by_subtype = {st: dict(cnt) for st, cnt in by_sev.items()}

    return (
        subtype_counts,
        device_counts_by_subtype,
        action_counts_by_subtype,
        severity_counts_by_subtype,
    )

def build_log_description_bar_data(dt_from=None, dt_to=None, top_n=10):
    """
    Barras por `log_description`:
      - logdesc_counts: { log_description: total } (TOP N)
      - device_counts_by_logdesc: { log_description: {device: n} }
      - action_counts_by_logdesc: { log_description: {action: n} }
      - severity_counts_by_logdesc: { log_description: {severity: n} }
    """
    qs = _base_qs(dt_from, dt_to)

    # Global (top N por frecuencia)
    rows = (
        qs.values("log_description")
          .annotate(total=Count("id"))
          .order_by("-total")[:top_n]
    )
    logdesc_counts = {(r["log_description"] or "N/A"): r["total"] for r in rows}

    # Por dispositivo
    by_dev = defaultdict(Counter)
    for r in qs.values("log_description", "device_name").annotate(total=Count("id")):
        desc = r["log_description"] or "N/A"
        dev = r["device_name"] or "N/A"
        by_dev[desc][dev] = r["total"]
    device_counts_by_logdesc = {d: dict(cnt) for d, cnt in by_dev.items()}

    # Por acción
    by_act = defaultdict(Counter)
    for r in qs.values("log_description", "actions").annotate(total=Count("id")):
        desc = r["log_description"] or "N/A"
        act = r["actions"] or "N/A"
        by_act[desc][act] = r["total"]
    action_counts_by_logdesc = {d: dict(cnt) for d, cnt in by_act.items()}

    # Por severidad
    by_sev = defaultdict(Counter)
    for r in qs.values("log_description", "severity").annotate(total=Count("id")):
        desc = r["log_description"] or "N/A"
        sev = r["severity"] if r["severity"] is not None else "N/A"
        by_sev[desc][sev] = r["total"]
    severity_counts_by_logdesc = {d: dict(cnt) for d, cnt in by_sev.items()}

    return (
        logdesc_counts,
        device_counts_by_logdesc,
        action_counts_by_logdesc,
        severity_counts_by_logdesc,
    )