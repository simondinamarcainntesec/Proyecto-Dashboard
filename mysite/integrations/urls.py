# integrations/urls.py
from django.urls import path
from integrations import views
from . import views_retell

app_name = "integrations"

urlpatterns = [
    path("obtener-alarmas/", views.obtener_alarmas_desde_api, name="obtener_alarmas"),
]
