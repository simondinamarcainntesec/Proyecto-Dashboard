# integrations/urls.py
from django.urls import path
from integrations import views

urlpatterns = [
    path("obtener-alarmas/", views.obtener_alarmas_desde_api, name="obtener_alarmas"),
]
