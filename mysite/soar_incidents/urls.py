from django.urls import path
from .views import (
    incidents_list,
    api_incidents_by_alarm_ids,
    switch_tenant,
    export_csv_current,
    export_csv_all,
    api_tenant_users,  # nuevo
)

app_name = "soar_incidents"

urlpatterns = [
    # Lista principal
    path("", incidents_list, name="list"),

    # Cambio de tenant desde la vista de incidentes
    path("switch-tenant/<int:tenant_id>/", switch_tenant, name="switch_tenant"),

    # Export CSV
    path("export/csv/current/", export_csv_current, name="export_csv_current"),
    path("export/csv/all/", export_csv_all, name="export_csv_all"),

    # API JSON para el dashboard SOAR
    path("api/by-alarm-ids/", api_incidents_by_alarm_ids, name="api_by_alarm_ids"),

    # API: usuarios por tenant (para el modal de asignación)
    path("api/tenant-users/", api_tenant_users, name="api_tenant_users"),
]
