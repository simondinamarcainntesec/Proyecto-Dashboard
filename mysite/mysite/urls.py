from django.contrib import admin
from django.urls import path, include
from django.shortcuts import render
from tenants.views import tenant_login_view, logout_view
from accounts.views import registro_cliente
from accounts import views as accounts_views
from tenants import views
from django.contrib.auth import views as auth_views

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
    path("config/notificaciones/", views.config_notificaciones_view, name="config_notificaciones"),

    # === APLICACIONES PRINCIPALES ===
    # Multi-tenant dashboards, histórico, realtime y cambio de tenant
    path("dashboard/", include(("dashboard.urls", "dashboard"), namespace="dashboard")),
    path("rest/oauth2-credential/callback", views.oauth2_callback, name="oauth2_callback"),

    # Ingesta API / Integraciones
    path("inyeccion_api/", include(("inyeccion_api.urls", "inyeccion_api"), namespace="inyeccion_api")),
    path("integrations/", include(("integrations.urls", "integrations"), namespace="integrations")),

    # Dashboards SOAR (Análisis e Incidentes)
    path("dashboard-soar/", include(("soar_dashboard.urls", "soar_dashboard"), namespace="soar_dashboard")),
    path("soar/incidentes/", include(("soar_incidents.urls", "soar_incidents"), namespace="soar_incidents")),
    path('auth/cambiar_contraseña/', views.cambiar_contraseña, name='cambiar_contrasena'),

    # ===== CAMBIO CONTRASEÑA ======
    path("auth/recuperar_contrasena/", accounts_views.recuperar_contrasena, name="recuperar_contrasena"),
        # Reset real (cuando el usuario entra al enlace del correo)
    path("auth/reset/<uidb64>/<token>/", auth_views.PasswordResetConfirmView.as_view(
        template_name="auth/password_reset_confirm.html",
        success_url="/auth/reset/done/"
    ), name="password_reset_confirm"),

    path("auth/reset/done/", auth_views.PasswordResetCompleteView.as_view(
        template_name="auth/password_reset_complete.html"
    ), name="password_reset_complete"),
]
