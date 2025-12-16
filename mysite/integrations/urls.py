# integrations/urls.py
from django.urls import path
from integrations import views
from . import views_retell

app_name = "integrations"

urlpatterns = [
    path("obtener-alarmas/", views.obtener_alarmas_desde_api, name="obtener_alarmas"),

    # Retell
    path("retell/create-web-call/", views_retell.retell_create_web_call, name="retell_create_web_call"),
    path("retell/get-call/<str:call_id>/", views_retell.retell_get_call, name="retell_get_call"),
]
