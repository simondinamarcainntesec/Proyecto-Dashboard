from django.urls import path
from . import views

app_name = "site24x7"

urlpatterns = [
    path("inn-monitor/status/", views.monitor_status, name="monitor_status"),
    path("inn-monitor/dashboard/", views.dashboard, name="dashboard"),
    path("anomalias/", views.anomaly_status, name="anomaly_status"),
    path("anomalias/detalle/", views.anomaly_detail, name="anomaly_detail"),  # opcional
]
