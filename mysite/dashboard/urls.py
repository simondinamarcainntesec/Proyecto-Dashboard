from django.urls import path
from . import views

urlpatterns = [
    path("", views.dashboard_view, name="index"),
    path("alarms/preview", views.alarms_preview, name="alarms_preview"),
    path("alarms/", views.alarms_table, name="alarms_table"),
    path("alarms/export.csv", views.alarms_export_csv, name="alarms_export_csv"),  # <- NUEVA
]
