# mysite/dashboard/charts.py
import logging
from collections import defaultdict, Counter
from django.db.models import Count
from django.db.models.functions import TruncDay
from inyeccion_api.models import Alarm  # ajusta si tu modelo está en otra app

logger = logging.getLogger(__name__)

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
          .values("date", "action")
          .annotate(total=Count("id"))
          .order_by("date")
    )

    trend_by_action = defaultdict(lambda: [0]*len(labels))
    for r in rows:
        date_str = r["date"].strftime("%Y-%m-%d")
        act = r["action"] or "N/A"
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
    """
    qs = _base_qs(dt_from, dt_to)

    rows = qs.values("device_name").annotate(total=Count("id")).order_by("-total")[:top_n]
    device_counts = {(r["device_name"] or "N/A"): r["total"] for r in rows}

    by_sev = defaultdict(Counter)
    for r in qs.values("severity", "device_name").annotate(total=Count("id")):
        sev = r["severity"] if r["severity"] is not None else "N/A"
        dev = r["device_name"] or "N/A"
        by_sev[sev][dev] = r["total"]

    device_counts_by_severity = {
        sev: dict(sorted(cnt.items(), key=lambda x: x[1], reverse=True)[:top_n])
        for sev, cnt in by_sev.items()
    }
    return device_counts, device_counts_by_severity

def build_action_bar_data(dt_from=None, dt_to=None, top_n=10):
    """
    (global, por_severidad) para barra Acciones y cross-filter.
    """
    qs = _base_qs(dt_from, dt_to)

    rows = qs.values("action").annotate(total=Count("id")).order_by("-total")[:top_n]
    action_counts = {(r["action"] or "N/A"): r["total"] for r in rows}

    by_sev = defaultdict(Counter)
    for r in qs.values("severity", "action").annotate(total=Count("id")):
        sev = r["severity"] if r["severity"] is not None else "N/A"
        act = r["action"] or "N/A"
        by_sev[sev][act] = r["total"]

    action_counts_by_severity = {
        sev: dict(sorted(cnt.items(), key=lambda x: x[1], reverse=True)[:top_n])
        for sev, cnt in by_sev.items()
    }
    return action_counts, action_counts_by_severity

def build_device_by_action(dt_from=None, dt_to=None, top_n=10):
    """
    Ranking de dispositivos por acción: { 'Open': {'DevA': n, ...}, 'Blocked': {...}, ... }
    """
    qs = _base_qs(dt_from, dt_to)

    by_action = defaultdict(Counter)
    rows = (
        qs.values("action", "device_name")
          .annotate(total=Count("id"))
          .order_by("-total")
    )
    for r in rows:
        act = r["action"] or "N/A"
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
