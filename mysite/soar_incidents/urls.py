from django.urls import path
from .views import incidents_list
from . import views

app_name = "soar_incidents"

urlpatterns = [
    path("", incidents_list, name="list"),
    path("switch-tenant/<int:tenant_id>/", views.switch_tenant, name="switch_tenant"),
]
