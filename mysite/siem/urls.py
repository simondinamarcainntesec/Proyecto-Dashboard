# siem/urls.py
from django.urls import path
from .views import alerts_logs360_view

app_name = "siem"

urlpatterns = [
    path("alerts/", alerts_logs360_view, name="alerts_logs360"),
]
