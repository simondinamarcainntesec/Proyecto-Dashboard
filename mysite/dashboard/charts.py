# dashboard/charts.py
from collections import defaultdict
from django.db.models import Count
from django.db.models.functions import TruncDay
from inyeccion_api.models import Alarm  # 👈 Import desde tu app real


def build_trend_data(dt_from=None, dt_to=None):
    """
    Construye datasets de tendencia temporal (por día) y por severidad.
    Usa el campo event_time del modelo Alarm.
    """
    qs = Alarm.objects.all()
    if dt_from and dt_to:
        qs = qs.filter(event_time__range=(dt_from, dt_to))

    # Agrupación por día
    daily = (
        qs.annotate(date=TruncDay('event_time'))
        .values('date')
        .annotate(total=Count('id'))
        .order_by('date')
    )

    trend_labels = [d['date'].strftime("%Y-%m-%d") for d in daily]
    trend_data = [d['total'] for d in daily]

    # Tendencias por severidad
    severity_qs = (
        qs.annotate(date=TruncDay('event_time'))
        .values('date', 'severity')
        .annotate(total=Count('id'))
        .order_by('date')
    )

    severity_trends = defaultdict(lambda: {"data": []})
    date_index = {date: idx for idx, date in enumerate(trend_labels)}

    # Inicializar con ceros
    for s in qs.values_list('severity', flat=True).distinct():
        severity_trends[s]["data"] = [0] * len(trend_labels)

    for row in severity_qs:
        date_str = row['date'].strftime("%Y-%m-%d")
        i = date_index.get(date_str)
        if i is not None:
            severity_trends[row['severity']]["data"][i] = row['total']

    return {
        "trend_labels": trend_labels,
        "trend_data": trend_data,
        "severity_trends": severity_trends,
    }


def build_donut_data(dt_from=None, dt_to=None):
    """
    Conteo por severidad para gráfico tipo dona.
    """
    qs = Alarm.objects.all()
    if dt_from and dt_to:
        qs = qs.filter(event_time__range=(dt_from, dt_to))

    return list(
        qs.values('severity')
        .annotate(total=Count('id'))
        .order_by('severity')
    )


def build_device_bar_data(dt_from=None, dt_to=None, top_n=10):
    """
    Conteo de alarmas por dispositivo (Top N).
    """
    qs = Alarm.objects.all()
    if dt_from and dt_to:
        qs = qs.filter(event_time__range=(dt_from, dt_to))

    return list(
        qs.values('device_name')
        .annotate(total=Count('id'))
        .order_by('-total')[:top_n]
    )


def build_action_bar_data(dt_from=None, dt_to=None, top_n=10):
    """
    Conteo de alarmas por acción o tipo de evento (Top N).
    """
    qs = Alarm.objects.all()
    if dt_from and dt_to:
        qs = qs.filter(event_time__range=(dt_from, dt_to))

    return list(
        qs.values('action')
        .annotate(total=Count('id'))
        .order_by('-total')[:top_n]
    )


def build_kpis(dt_from=None, dt_to=None):
    """
    KPIs principales (totales y críticos)
    """
    qs = Alarm.objects.all()
    if dt_from and dt_to:
        qs = qs.filter(event_time__range=(dt_from, dt_to))

    total = qs.count()
    high = qs.filter(severity='High').count()
    dispositivos = qs.values('device_name').distinct().count()

    return {
        "kpi_total": total,
        "kpi_high": high,
        "kpi_dispositivos": dispositivos,
    }
