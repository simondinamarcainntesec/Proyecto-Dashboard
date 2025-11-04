from django.contrib import admin
from django.urls import path, include
from django.shortcuts import render
from tenants.views import tenant_login_view, logout_view
from accounts.views import registro_cliente
from tenants import views

# === HOME ===
def home_view(request):
    return render(request, "home/home.html")

urlpatterns = [
    # === ADMIN ===
    path("admin/", admin.site.urls),

    # === AUTENTICACIÓN / REGISTRO ===
    path("", tenant_login_view, name="login"),
    path("login/", tenant_login_view, name="login"),
    path("auth/login/", tenant_login_view, name="auth_login"),
    path("logout/", logout_view, name="logout"),
    path("auth/registro_cliente/", registro_cliente, name="auth_registro_cliente"),

    # === APLICACIONES PRINCIPALES ===
    # Multi-tenant dashboards, histórico, realtime y cambio de tenant
    path("dashboard/", include(("dashboard.urls", "dashboard"), namespace="dashboard")),

    # Ingesta API / Integraciones
    path("inyeccion_api/", include(("inyeccion_api.urls", "inyeccion_api"), namespace="inyeccion_api")),
    path("integrations/", include(("integrations.urls", "integrations"), namespace="integrations")),

    # Dashboards SOAR (Análisis e Incidentes)
    path("dashboard-soar/", include(("soar_dashboard.urls", "soar_dashboard"), namespace="soar_dashboard")),
    path("soar/incidentes/", include(("soar_incidents.urls", "soar_incidents"), namespace="soar_incidents")),
    path('auth/cambiar_contraseña/', views.cambiar_contraseña, name='cambiar_contraseña'),
]
