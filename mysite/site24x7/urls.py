from django.urls import path
from . import views

app_name = "site24x7"

urlpatterns = [
    path("inn-monitor/status/", views.monitor_status, name="monitor_status"),
    path("inn-monitor/dashboard/", views.dashboard, name="dashboard"),
]
