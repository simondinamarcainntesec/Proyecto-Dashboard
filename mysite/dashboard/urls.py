# dashboard/urls.py
from django.urls import path
from .views import dashboard_view
from . import realtime
from .realtime import (
    realtime_alarms_by_subtype,
    realtime_alarm_log_table,
)

urlpatterns = [
    # Histórico (ya lo usas con reverse("dashboard_alarmsone"))
    path("alarmsone/", dashboard_view, name="dashboard_alarmsone"),

    # Realtime (página)
    path("realtime/", realtime.realtime_page, name="dashboard_realtime"),

    # Raíz del dashboard
    path("", dashboard_view, name="dashboard"),

    # ====== NUEVOS ENDPOINTS PARA LOS MODALES ======
    path("realtime/alarms", realtime_alarms_by_subtype, name="realtime_alarms_by_subtype"),
    path("realtime/alarms/", realtime_alarms_by_subtype),  # acepta slash final

    path("realtime/alarm-log", realtime_alarm_log_table, name="realtime_alarm_log_table"),
    path("realtime/alarm-log/", realtime_alarm_log_table),
]
