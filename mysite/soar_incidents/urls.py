from django.urls import path
from .views import incidents_list, api_incidents_by_alarm_ids, switch_tenant

app_name = "soar_incidents"

urlpatterns = [
    path("", incidents_list, name="list"),
    path("switch-tenant/<int:tenant_id>/", switch_tenant, name="switch_tenant"),

    # API JSON para consumir desde el dashboard SOAR:
    # /soar/incidentes/api/by-alarm-ids/?alarm_ids=ID1,ID2,ID3
    path("api/by-alarm-ids/", api_incidents_by_alarm_ids, name="api_by_alarm_ids"),
]
