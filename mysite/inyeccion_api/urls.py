# mysite/dashboard/urls.py
from django.urls import path, include
from . import views

urlpatterns = [
    path("", views.inyeccion_api_view, name="index"),
    path("alarms/preview", views.alarms_preview, name="alarms_preview"),
    path("alarms/", views.alarms_table, name="alarms_table"),
    path("alarms/export.csv", views.alarms_export_csv, name="alarms_export_csv"),
    path("", include("dashboard.urls")),
    
]