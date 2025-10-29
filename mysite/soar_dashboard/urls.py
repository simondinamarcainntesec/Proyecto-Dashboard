from django.urls import path
from .views import dashboard_soar

app_name = "soar_dashboard"

urlpatterns = [
    path("dashboard/", dashboard_soar, name="dashboard"),
]
