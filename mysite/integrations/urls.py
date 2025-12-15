# integrations/urls.py
from django.urls import path
from integrations import views
from .views_retell import retell_create_web_call

urlpatterns = [
    path("obtener-alarmas/", views.obtener_alarmas_desde_api, name="obtener_alarmas"),
    path("retell/create-web-call/", retell_create_web_call, name="retell_create_web_call"),
]
