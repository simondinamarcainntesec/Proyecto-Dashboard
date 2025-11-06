from django.urls import path
from .views import dashboard_view, switch_tenant
from . import realtime
from . import views

from .realtime import (
    realtime_alarms_by_subtype,
    realtime_alarm_log_table,
)
app_name = "dashboard"
urlpatterns = [
    # Dashboard principal (histórico)
    path("alarmsone/", dashboard_view, name="dashboard_alarmsone"),
    path("realtime/", realtime.realtime_page, name="dashboard_realtime"),
    path("", dashboard_view, name="dashboard"),
    path("dashboard/realtime/alarms", realtime.realtime_alarms_by_subtype, name="realtime_alarms_by_subtype"),
    path("dashboard/realtime/alarm-log", realtime.realtime_alarm_log_table, name="realtime_alarm_log_table"),

    # --- Cambio de tenant ---
    path("switch-tenant/<int:tenant_id>/", views.switch_tenant, name="switch_tenant"),
    path("dashboard/switch-tenant/<int:tenant_id>/", views.switch_tenant, name="switch_tenant"),



    # --- Endpoints de realtime ---
    path("realtime/alarms", realtime_alarms_by_subtype, name="realtime_alarms_by_subtype"),
    path("realtime/alarms/", realtime_alarms_by_subtype),
    path("realtime/alarm-log", realtime_alarm_log_table, name="realtime_alarm_log_table"),
    path("realtime/alarm-log/", realtime_alarm_log_table),
]
