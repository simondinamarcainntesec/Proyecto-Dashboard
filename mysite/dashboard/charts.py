import logging
from collections import defaultdict, Counter
from datetime import timedelta
import pytz
import re

from django.db.models import Count
from django.db.models.functions import TruncDay, TruncHour

from inyeccion_api.models import Alarm
from tenants.context import current_tenant  # Importar model de alarmas

logger = logging.getLogger(__name__)

# TZ local para el dashboard
CL_TZ = pytz.timezone("America/Santiago")


# ----------------------------
# Helpers de normalización
# ----------------------------
def _norm_sev(val):
    s = (val or "").strip()
    return s.lower() if s else "n/a"


def _norm_msg_sev(val):
    s = (val or "").strip()
    return s.lower() if s else "n/a"


def _norm_act(val):
    # No forzamos lowercase aquí (el front ya normaliza),
    # pero convertimos None/"" en "N/A" para evitar claves vacías en dicts
    s = (val or "").strip()
    return s if s else "N/A"


def _norm_dev(val):
    s = (val or "").strip()
    return s if s else "N/A"


def _norm_level(val):
    # Para level usamos el valor tal cual, pero aseguramos "N/A" si falta
    s = (val or "").strip()
    return s if s else "N/A"


def _norm_subtype(val):
    s = (val or "").strip()
    return s if s else "N/A"


def _base_qs(dt_from=None, dt_to=None):
    """
    Scoping por tenant:
      - Si Alarm tiene FK tenant -> filtra por tenant.
      - Si NO, usa Tenant.alarms_one_id y filtra por tags (AOTAGS).
    Rango [dt_from, dt_to) (to exclusivo).
    """
    t = current_tenant.get()
    base = getattr(Alarm, "all_objects", Alarm.objects).all()
    if t is None:
        logger.warning("[Charts] _base_qs sin tenant → vacío")
        return base.none()

    # 1) Si el modelo Alarm ya tiene FK tenant, úsalo
    if "tenant" in [f.name for f in Alarm._meta.get_fields()]:
        qs = base.filter(tenant=t)
    else:
        # 2) Fallback: matchear AOTAGS (Tenant.alarms_one_id) dentro de Alarm.tags
        aotag = (t.alarms_one_id or "").strip()
        if not aotag:
            logger.warning("[Charts] Tenant %s no tiene alarms_one_id → vacío", t.name)
            return base.none()

        pattern = rf"(^|,)\s*{re.escape(aotag)}\s*(,|$)"
        qs = base.filter(tags__regex=pattern)

    if dt_from and dt_to:
        qs = qs.filter(event_time__gte=dt_from, event_time__lt=dt_to)
    return qs



# =========================
# === TENDENCIA POR DÍA ===
# =========================
def build_trend_data(dt_from=None, dt_to=None):
    """
    Eje temporal (por día) y series por severidad (normalizada).
    """
    qs = _base_qs(dt_from, dt_to)

    # Eje temporal base (en TZ local)
    daily = (
        qs.annotate(date=TruncDay("event_time", tzinfo=CL_TZ))
        .values("date")
        .annotate(total=Count("id"))
        .order_by("date")
    )
    trend_labels = [d["date"].strftime("%Y-%m-%d") for d in daily]
    idx = {d: i for i, d in enumerate(trend_labels)}
    trend_data = [0] * len(trend_labels)
    for d in daily:
        i = idx.get(d["date"].strftime("%Y-%m-%d"))
        if i is not None:
            trend_data[i] = d["total"]

    # Series por severidad (en TZ local + normalización)
    severity_qs = (
        qs.annotate(date=TruncDay("event_time", tzinfo=CL_TZ))
        .values("date", "severity")
        .annotate(total=Count("id"))
        .order_by("date")
    )
    severities = list(qs.values_list("severity", flat=True).distinct())
    severities = [_norm_sev(s) for s in severities]

    severity_trends = {s: {"data": [0] * len(trend_labels)} for s in severities}
    for row in severity_qs:
        date_str = row["date"].strftime("%Y-%m-%d")
        sev = _norm_sev(row["severity"])
        i = idx.get(date_str)
        if i is not None:
            severity_trends.setdefault(sev, {"data": [0] * len(trend_labels)})
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

    top = (
        qs.values("device_name")
        .annotate(total=Count("id"))
        .order_by("-total")[:top_n]
    )
    # Usar valores RAW para filtrar; normalizar solo para las claves de salida.
    top_raw = [r["device_name"] for r in top]
    top_devices = [_norm_dev(r["device_name"]) for r in top]

    daily = (
        qs.annotate(date=TruncDay("event_time", tzinfo=CL_TZ))
        .values("date")
        .annotate(total=Count("id"))
        .order_by("date")
    )
    labels = [d["date"].strftime("%Y-%m-%d") for d in daily]
    idx = {d: i for i, d in enumerate(labels)}

    device_rows = (
        qs.filter(device_name__in=[None] + top_raw)  # cubrir N/A si corresponde
        .annotate(date=TruncDay("event_time", tzinfo=CL_TZ))
        .values("date", "device_name")
        .annotate(total=Count("id"))
        .order_by("date")
    )
    trend_by_device = {dev: [0] * len(labels) for dev in top_devices}
    for r in device_rows:
        date_str = r["date"].strftime("%Y-%m-%d")
        dev = _norm_dev(r["device_name"])
        if dev in trend_by_device:
            i = idx.get(date_str)
            if i is not None:
                trend_by_device[dev][i] = r["total"]

    return {"trend_by_device": trend_by_device, "top_devices": top_devices}


def build_trend_by_action(dt_from=None, dt_to=None):
    """
    Series por día para cada acción (usa 'actions').
    """
    qs = _base_qs(dt_from, dt_to)

    daily = (
        qs.annotate(date=TruncDay("event_time", tzinfo=CL_TZ))
        .values("date")
        .annotate(total=Count("id"))
        .order_by("date")
    )
    labels = [d["date"].strftime("%Y-%m-%d") for d in daily]
    idx = {d: i for i, d in enumerate(labels)}

    rows = (
        qs.annotate(date=TruncDay("event_time", tzinfo=CL_TZ))
        .values("date", "actions")
        .annotate(total=Count("id"))
        .order_by("date")
    )

    trend_by_action = defaultdict(lambda: [0] * len(labels))
    for r in rows:
        date_str = r["date"].strftime("%Y-%m-%d")
        act = _norm_act(r["actions"])
        i = idx.get(date_str)
        if i is not None:
            trend_by_action[act][i] = r["total"]

    return {"trend_by_action": dict(trend_by_action), "trend_labels": labels}


# ==================
# === AGREGADOS  ===
# ==================
def build_donut_data(dt_from=None, dt_to=None):
    """
    Dict {severity(normalizada): total}
    """
    qs = _base_qs(dt_from, dt_to)
    raw = qs.values("severity").annotate(total=Count("id")).order_by("severity")
    out = {}
    for r in raw:
        k = _norm_sev(r["severity"])
        out[k] = r["total"]
    return out


def build_device_bar_data(dt_from=None, dt_to=None, top_n=10):
    """
    (global, por_severidad) para tabla y cross-filter.
    Además devuelve el mapa COMPLETO severidad->device (sin top_n)
    para que el front pueda filtrar correctamente el donut.
    """
    qs = _base_qs(dt_from, dt_to)

    rows = qs.values("device_name").annotate(total=Count("id")).order_by("-total")[:top_n]
    device_counts = {_norm_dev(r["device_name"]): r["total"] for r in rows}

    by_sev = defaultdict(Counter)
    for r in qs.values("severity", "device_name").annotate(total=Count("id")):
        sev = _norm_sev(r["severity"])
        dev = _norm_dev(r["device_name"])
        by_sev[sev][dev] = r["total"]

    # full (sin recortar)
    device_counts_by_severity_full = {sev: dict(cnt) for sev, cnt in by_sev.items()}

    # recortado a top_n (para UI)
    device_counts_by_severity = {
        sev: dict(sorted(cnt.items(), key=lambda x: x[1], reverse=True)[:top_n])
        for sev, cnt in by_sev.items()
    }
    return device_counts, device_counts_by_severity, device_counts_by_severity_full


def build_action_bar_data(dt_from=None, dt_to=None, top_n=10):
    """
    (global, por_severidad) para barra Acciones y cross-filter.
    """
    qs = _base_qs(dt_from, dt_to)

    rows = (
        qs.values("actions")
        .annotate(total=Count("id"))
        .order_by("-total")[:top_n]
    )
    action_counts = {_norm_act(r["actions"]): r["total"] for r in rows}

    by_sev = defaultdict(Counter)
    for r in qs.values("severity", "actions").annotate(total=Count("id")):
        sev = _norm_sev(r["severity"])
        act = _norm_act(r["actions"])
        by_sev[sev][act] = r["total"]

    action_counts_by_severity = {
        sev: dict(sorted(cnt.items(), key=lambda x: x[1], reverse=True)[:top_n])
        for sev, cnt in by_sev.items()
    }

    # Acciones por dispositivo (para filtrar el bar al click en la tabla)
    by_dev = defaultdict(Counter)
    for r in _base_qs(dt_from, dt_to).values("device_name", "actions").annotate(total=Count("id")):
        dev = _norm_dev(r["device_name"])
        act = _norm_act(r["actions"])
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
        qs.values("actions", "device_name")
        .annotate(total=Count("id"))
        .order_by("-total")
    )
    for r in rows:
        act = _norm_act(r["actions"])
        dev = _norm_dev(r["device_name"])
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


# =========================
# === HORA (00..23)    ===
# =========================
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

    # 2) Por severidad y hora (normalizada)
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
            sev = _norm_sev(r["severity"])
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
            dev = _norm_dev(r["device_name"])
            device_counts_by_hour_full[hour][dev] += r["total"]
    device_counts_by_hour = {
        h: dict(sorted(m.items(), key=lambda x: x[1], reverse=True)[:top_n])
        for h, m in device_counts_by_hour_full.items()
    }
    device_counts_by_hour_full = {h: dict(m) for h, m in device_counts_by_hour_full.items()}

    # 4) Por acción y hora  (usa 'actions')
    act_rows = (
        qs.annotate(h=TruncHour("event_time", tzinfo=CL_TZ))
        .values("h", "actions")
        .annotate(total=Count("id"))
    )
    action_counts_by_hour = defaultdict(lambda: defaultdict(int))
    for r in act_rows:
        h = r.get("h")
        if h:
            hour = h.strftime("%H")
            act = _norm_act(r["actions"])
            action_counts_by_hour[hour][act] += r["total"]
    action_counts_by_hour = {h: dict(m) for h, m in action_counts_by_hour.items()}

    # 5) Trend por día + hora (en TZ local)
    daily = (
        qs.annotate(date=TruncDay("event_time", tzinfo=CL_TZ), h=TruncHour("event_time", tzinfo=CL_TZ))
        .values("date", "h")
        .annotate(total=Count("id"))
        .order_by("date")
    )
    trend_dates = sorted({r["date"] for r in daily if r.get("date")})
    trend_labels = [d.strftime("%Y-%m-%d") for d in trend_dates]
    idx = {d: i for i, d in enumerate(trend_labels)}
    trend_by_hour = {f"{i:02d}": [0] * len(trend_labels) for i in range(24)}

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
        "device_counts_by_hour": device_counts_by_hour,
        "device_counts_by_hour_full": device_counts_by_hour_full,
        "action_counts_by_hour": action_counts_by_hour,
        "trend_labels_hour": trend_labels,
        "trend_by_hour": trend_by_hour,
    }


# =========================
# === msg_severity
# =========================
def build_msg_severity_bar_data(dt_from=None, dt_to=None, top_n=10):
    qs = _base_qs(dt_from, dt_to)

    rows = qs.values("msg_severity").annotate(total=Count("id")).order_by("-total")[:top_n]
    msg_severity_counts = {(_norm_msg_sev(r["msg_severity"])): r["total"] for r in rows}

    by_msg_dev = defaultdict(Counter)
    for r in qs.values("msg_severity", "device_name").annotate(total=Count("id")):
        msg = _norm_msg_sev(r["msg_severity"])
        dev = _norm_dev(r["device_name"])
        by_msg_dev[msg][dev] = r["total"]
    device_counts_by_msg_severity = {msg: dict(cnt) for msg, cnt in by_msg_dev.items()}

    by_msg_act = defaultdict(Counter)
    for r in qs.values("msg_severity", "actions").annotate(total=Count("id")):
        msg = _norm_msg_sev(r["msg_severity"])
        act = _norm_act(r["actions"])
        by_msg_act[msg][act] = r["total"]
    action_counts_by_msg_severity = {msg: dict(cnt) for msg, cnt in by_msg_act.items()}

    by_msg_sev = defaultdict(Counter)
    for r in qs.values("msg_severity", "severity").annotate(total=Count("id")):
        msg = _norm_msg_sev(r["msg_severity"])
        sev = _norm_sev(r["severity"])
        by_msg_sev[msg][sev] = r["total"]
    severity_counts_by_msg_severity = {msg: dict(cnt) for msg, cnt in by_msg_sev.items()}

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
            msg = _norm_msg_sev(r["msg_severity"])
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
    qs = _base_qs(dt_from, dt_to)

    daily = (
        qs.annotate(date=TruncDay("event_time", tzinfo=CL_TZ))
        .values("date")
        .annotate(total=Count("id"))
        .order_by("date")
    )
    labels = [d["date"].strftime("%Y-%m-%d") for d in daily]
    idx = {d: i for i, d in enumerate(labels)}

    rows = (
        qs.annotate(date=TruncDay("event_time", tzinfo=CL_TZ))
        .values("date", "msg_severity")
        .annotate(total=Count("id"))
        .order_by("date")
    )

    trend_by_msg_severity = defaultdict(lambda: [0] * len(labels))
    for r in rows:
        date_str = r["date"].strftime("%Y-%m-%d")
        msg = _norm_msg_sev(r["msg_severity"])
        i = idx.get(date_str)
        if i is not None:
            trend_by_msg_severity[msg][i] = r["total"]

    return {"trend_by_msg_severity": dict(trend_by_msg_severity), "trend_labels": labels}


# =============================
# === LEVEL / SUBTYPE / LOG ===
# =============================
def build_level_bar_data(dt_from=None, dt_to=None, top_n=10):
    qs = _base_qs(dt_from, dt_to)

    rows = qs.values("level").annotate(total=Count("id")).order_by("-total")[:top_n]
    level_counts = {(r["level"] or "N/A"): r["total"] for r in rows}

    by_dev = defaultdict(Counter)
    for r in qs.values("level", "device_name").annotate(total=Count("id")):
        lvl = _norm_level(r["level"])
        dev = _norm_dev(r["device_name"])
        by_dev[lvl][dev] = r["total"]
    device_counts_by_level = {lvl: dict(cnt) for lvl, cnt in by_dev.items()}

    by_act = defaultdict(Counter)
    for r in qs.values("level", "actions").annotate(total=Count("id")):
        lvl = _norm_level(r["level"])
        act = _norm_act(r["actions"])
        by_act[lvl][act] = r["total"]
    action_counts_by_level = {lvl: dict(cnt) for lvl, cnt in by_act.items()}

    by_sev = defaultdict(Counter)
    for r in qs.values("level", "severity").annotate(total=Count("id")):
        lvl = _norm_level(r["level"])
        sev = _norm_sev(r["severity"])
        by_sev[lvl][sev] = r["total"]
    severity_counts_by_level = {lvl: dict(cnt) for lvl, cnt in by_sev.items()}

    return (
        level_counts,
        device_counts_by_level,
        action_counts_by_level,
        severity_counts_by_level,
    )


def build_subtype_bar_data(dt_from=None, dt_to=None, top_n=10):
    qs = _base_qs(dt_from, dt_to)

    rows = qs.values("subtype").annotate(total=Count("id")).order_by("-total")[:top_n]
    subtype_counts = {(r["subtype"] or "N/A"): r["total"] for r in rows}

    by_dev = defaultdict(Counter)
    for r in qs.values("subtype", "device_name").annotate(total=Count("id")):
        st = _norm_subtype(r["subtype"])
        dev = _norm_dev(r["device_name"])
        by_dev[st][dev] = r["total"]
    device_counts_by_subtype = {st: dict(cnt) for st, cnt in by_dev.items()}

    by_act = defaultdict(Counter)
    for r in qs.values("subtype", "actions").annotate(total=Count("id")):
        st = _norm_subtype(r["subtype"])
        act = _norm_act(r["actions"])
        by_act[st][act] = r["total"]
    action_counts_by_subtype = {st: dict(cnt) for st, cnt in by_act.items()}

    by_sev = defaultdict(Counter)
    for r in qs.values("subtype", "severity").annotate(total=Count("id")):
        st = _norm_subtype(r["subtype"])
        sev = _norm_sev(r["severity"])
        by_sev[st][sev] = r["total"]
    severity_counts_by_subtype = {st: dict(cnt) for st, cnt in by_sev.items()}

    return (
        subtype_counts,
        device_counts_by_subtype,
        action_counts_by_subtype,
        severity_counts_by_subtype,
    )


# === TREND POR SUBTYPE (para cruzar Subtype -> Trend) ===
def build_trend_by_subtype(dt_from=None, dt_to=None):
    """
    Devuelve:
      {
        "trend_labels": ["YYYY-MM-DD", ...],
        "trend_by_subtype": { subtype: [c1, c2, ...], ... }
      }
    """
    qs = _base_qs(dt_from, dt_to)

    daily = (
        qs.annotate(date=TruncDay("event_time", tzinfo=CL_TZ))
          .values("date")
          .annotate(total=Count("id"))
          .order_by("date")
    )
    labels = [d["date"].strftime("%Y-%m-%d") for d in daily]
    idx = {d: i for i, d in enumerate(labels)}

    rows = (
        qs.annotate(date=TruncDay("event_time", tzinfo=CL_TZ))
          .values("date", "subtype")
          .annotate(total=Count("id"))
          .order_by("date")
    )

    trend_by_subtype = defaultdict(lambda: [0] * len(labels))
    for r in rows:
        date_str = r["date"].strftime("%Y-%m-%d")
        st = (r["subtype"] or "N/A")
        i = idx.get(date_str)
        if i is not None:
            trend_by_subtype[st][i] = r["total"]

    return {"trend_labels": labels, "trend_by_subtype": dict(trend_by_subtype)}


# === HOURLY POR SUBTYPE (para cruzar Subtype -> Hourly) ===
def build_subtype_counts_by_hour(dt_from=None, dt_to=None):
    """
    Devuelve:
      { "00": { subtype: n, ... }, "01": {...}, ..., "23": {...} }
    En TZ local.
    """
    qs = _base_qs(dt_from, dt_to)

    by_hour = defaultdict(Counter)

    rows = (
        qs.annotate(h=TruncHour("event_time", tzinfo=CL_TZ))
          .values("h", "subtype")
          .annotate(total=Count("id"))
    )
    for r in rows:
        h = r.get("h")
        if not h:
            continue
        hour = h.strftime("%H")
        st = (r["subtype"] or "N/A")
        by_hour[hour][st] += r["total"]

    return {h: dict(cnt) for h, cnt in by_hour.items()}


def build_log_description_bar_data(dt_from=None, dt_to=None, top_n=10):
    """
    Barras por `log_description`:
      - logdesc_counts: { log_description: total } (TOP N)
      - device_counts_by_logdesc: { log_description: {device: n} }
      - action_counts_by_logdesc: { log_description: {action: n} }
      - severity_counts_by_logdesc: { log_description: {severity: n} }
    """
    qs = _base_qs(dt_from, dt_to)

    rows = (
        qs.values("log_description")
        .annotate(total=Count("id"))
        .order_by("-total")[:top_n]
    )
    logdesc_counts = {(r["log_description"] or "N/A"): r["total"] for r in rows}

    by_dev = defaultdict(Counter)
    for r in qs.values("log_description", "device_name").annotate(total=Count("id")):
        desc = (r["log_description"] or "N/A").strip() or "N/A"
        dev = _norm_dev(r["device_name"])
        by_dev[desc][dev] = r["total"]
    device_counts_by_logdesc = {d: dict(cnt) for d, cnt in by_dev.items()}

    by_act = defaultdict(Counter)
    for r in qs.values("log_description", "actions").annotate(total=Count("id")):
        desc = (r["log_description"] or "N/A").strip() or "N/A"
        act = _norm_act(r["actions"])
        by_act[desc][act] = r["total"]
    action_counts_by_logdesc = {d: dict(cnt) for d, cnt in by_act.items()}

    by_sev = defaultdict(Counter)
    for r in qs.values("log_description", "severity").annotate(total=Count("id")):
        desc = (r["log_description"] or "N/A").strip() or "N/A"
        sev = _norm_sev(r["severity"])
        by_sev[desc][sev] = r["total"]
    severity_counts_by_logdesc = {d: dict(cnt) for d, cnt in by_sev.items()}

    return (
        logdesc_counts,
        device_counts_by_logdesc,
        action_counts_by_logdesc,
        severity_counts_by_logdesc,
    )


# =======================================================
# === NUEVOS CONTRATOS para filtrado por LEVEL completo ==
# =======================================================
def build_trend_by_level(dt_from=None, dt_to=None):
    """
    Devuelve un dict: { level: [serie diaria alineada a trend_labels] }
    Las etiquetas de fecha (trend_labels) ya las construye build_trend_data;
    no es necesario repetirlas aquí en el contexto.
    """
    qs = _base_qs(dt_from, dt_to)

    # Eje (fechas) para indexar
    daily = (
        qs.annotate(date=TruncDay("event_time", tzinfo=CL_TZ))
        .values("date")
        .annotate(total=Count("id"))
        .order_by("date")
    )
    labels = [d["date"].strftime("%Y-%m-%d") for d in daily]
    idx = {d: i for i, d in enumerate(labels)}

    rows = (
        qs.annotate(date=TruncDay("event_time", tzinfo=CL_TZ))
        .values("date", "level")
        .annotate(total=Count("id"))
        .order_by("date")
    )

    trend_by_level = defaultdict(lambda: [0] * len(labels))
    for r in rows:
        date_str = r["date"].strftime("%Y-%m-%d")
        lvl = _norm_level(r["level"])
        i = idx.get(date_str)
        if i is not None:
            trend_by_level[lvl][i] = r["total"]

    return {"trend_by_level": dict(trend_by_level)}


def build_level_counts_by_hour(dt_from=None, dt_to=None):
    """
    Dict con forma: { "00": { level: count, ... }, "01": {...}, ... }
    (los buckets están en TZ local)
    """
    qs = _base_qs(dt_from, dt_to)

    rows = (
        qs.annotate(h=TruncHour("event_time", tzinfo=CL_TZ))
        .values("h", "level")
        .annotate(total=Count("id"))
        .order_by("h")
    )

    out = defaultdict(lambda: defaultdict(int))
    for r in rows:
        h = r.get("h")
        if not h:
            continue
        hour = h.strftime("%H")
        lvl = _norm_level(r["level"])
        out[hour][lvl] += r["total"]

    return {"level_counts_by_hour": {h: dict(m) for h, m in out.items()}}


def build_subtype_counts_by_level(dt_from=None, dt_to=None):
    """
    Dict con forma: { level: { subtype: count, ... }, ... }
    """
    qs = _base_qs(dt_from, dt_to)

    rows = (
        qs.values("level", "subtype")
        .annotate(total=Count("id"))
        .order_by("level", "-total")
    )

    out = defaultdict(lambda: defaultdict(int))
    for r in rows:
        lvl = _norm_level(r["level"])
        st = _norm_subtype(r["subtype"])
        out[lvl][st] += r["total"]

    # cast a dict normal
    return {"subtype_counts_by_level": {lvl: dict(cnt) for lvl, cnt in out.items()}}


# === LEVEL POR SUBTYPE (para cruzar Subtype -> Level) ===
def build_level_counts_by_subtype(dt_from=None, dt_to=None, top_n=None):
    """
    Devuelve:
      { subtype: { level: total, ... }, ... }

    Si top_n es int, recorta los levels por subtype a los más frecuentes.
    """
    qs = _base_qs(dt_from, dt_to)
    by_subtype = defaultdict(Counter)

    rows = (
        qs.values("subtype", "level")
          .annotate(total=Count("id"))
    )
    for r in rows:
        st  = (r["subtype"] or "N/A")
        lvl = (r["level"] or "N/A")
        by_subtype[st][lvl] = r["total"]

    if isinstance(top_n, int) and top_n > 0:
        return {
            st: dict(sorted(cnt.items(), key=lambda x: x[1], reverse=True)[:top_n])
            for st, cnt in by_subtype.items()
        }
    return {st: dict(cnt) for st, cnt in by_subtype.items()}

# === MSG_SEVERITY por LEVEL/SUBTYPE (para cruzar Level/Subtype -> msg_severity) ===
def build_msg_severity_by_level(dt_from=None, dt_to=None):
    """
    Devuelve: { level: { msg_severity(normalizada): total, ... }, ... }
    """
    qs = _base_qs(dt_from, dt_to)
    rows = (
        qs.values("level", "msg_severity")
          .annotate(total=Count("id"))
          .order_by("level", "-total")
    )
    from collections import defaultdict, Counter
    out = defaultdict(Counter)
    for r in rows:
        lvl = _norm_level(r["level"])
        msg = _norm_msg_sev(r["msg_severity"])
        out[lvl][msg] += r["total"]
    return {"msg_severity_by_level": {lvl: dict(cnt) for lvl, cnt in out.items()}}


def build_msg_severity_by_subtype(dt_from=None, dt_to=None):
    """
    Devuelve: { subtype: { msg_severity(normalizada): total, ... }, ... }
    """
    qs = _base_qs(dt_from, dt_to)
    rows = (
        qs.values("subtype", "msg_severity")
          .annotate(total=Count("id"))
          .order_by("subtype", "-total")
    )
    from collections import defaultdict, Counter
    out = defaultdict(Counter)
    for r in rows:
        st = _norm_subtype(r["subtype"])
        msg = _norm_msg_sev(r["msg_severity"])
        out[st][msg] += r["total"]
    return {"msg_severity_by_subtype": {st: dict(cnt) for st, cnt in out.items()}}

from collections import defaultdict, Counter

def build_level_by_msg_severity(dt_from=None, dt_to=None):
    """
    { msg_severity: { level: total, ... }, ... }
    """
    qs = _base_qs(dt_from, dt_to)
    rows = (
        qs.values("msg_severity", "level")
          .annotate(total=Count("id"))
    )
    out = defaultdict(Counter)
    for r in rows:
        msg = _norm_msg_sev(r["msg_severity"])
        lvl = _norm_level(r["level"])
        out[msg][lvl] += r["total"]
    return {"level_by_msg_severity": {msg: dict(cnt) for msg, cnt in out.items()}}


def build_subtype_by_msg_severity(dt_from=None, dt_to=None):
    """
    { msg_severity: { subtype: total, ... }, ... }
    """
    qs = _base_qs(dt_from, dt_to)
    rows = (
        qs.values("msg_severity", "subtype")
          .annotate(total=Count("id"))
    )
    out = defaultdict(Counter)
    for r in rows:
        msg = _norm_msg_sev(r["msg_severity"])
        st  = _norm_subtype(r["subtype"])
        out[msg][st] += r["total"]
    return {"subtype_by_msg_severity": {msg: dict(cnt) for msg, cnt in out.items()}}

def build_hour_series_by_subtype(dt_from=None, dt_to=None):
    """
    Devuelve: { subtype: [c00, c01, ..., c23] } en TZ America/Santiago,
    alineado a las mismas 24 etiquetas "00".."23".
    """
    qs = _base_qs(dt_from, dt_to)

    # base 24 horas
    hour_labels = [f"{i:02d}" for i in range(24)]
    index = {h: i for i, h in enumerate(hour_labels)}

    # contar por hora y subtype
    rows = (
        qs.annotate(h=TruncHour("event_time", tzinfo=CL_TZ))
          .values("h", "subtype")
          .annotate(total=Count("id"))
    )

    from collections import defaultdict
    series = defaultdict(lambda: [0] * 24)

    for r in rows:
        h = r.get("h")
        if not h:
            continue
        hour = h.strftime("%H")
        st = _norm_subtype(r["subtype"])
        pos = index.get(hour)
        if pos is not None:
            series[st][pos] += r["total"]

    return {"hour_series_by_subtype": dict(series)}


