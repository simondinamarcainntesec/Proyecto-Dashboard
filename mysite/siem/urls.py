# mysite/siem/urls.py
from django.urls import path
from . import views

app_name = "siem"

urlpatterns = [
    # Logs360
    path("alerts/", views.alerts_logs360_view, name="alerts_logs360"),

    # Dashboards (iframes desde tenants_tenantdashboardembed)
    path("threat-analytics/", views.threat_analytics, name="threat_analytics"),
    path("microsoft365/", views.microsoft365, name="microsoft365"),
    path("networks/", views.networks, name="networks"),
    path("eventos-diarios/", views.eventos_diarios, name="eventos_diarios"),
]