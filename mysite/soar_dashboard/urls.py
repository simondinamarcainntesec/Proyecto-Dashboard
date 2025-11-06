from django.urls import path
from .views import dashboard_soar
from tenants import views as tenant_views

app_name = "soar_dashboard"

urlpatterns = [
    path("dashboard/", dashboard_soar, name="dashboard"),
    path("dashboard/switch-tenant/<int:tenant_id>/", tenant_views.switch_tenant, name="switch_tenant"),

]
