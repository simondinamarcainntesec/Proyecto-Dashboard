from django.contrib import admin
from django.urls import path, include
from django.shortcuts import render, redirect
from django.views.generic import RedirectView

from tenants.views import tenant_login_view, logout_view
from accounts.views import registro_cliente
from accounts import views as accounts_views
from tenants import views
from django.contrib.auth import views as auth_views
from home import views as home_views

# 2FA (django-two-factor-auth)
from two_factor.urls import urlpatterns as tf_urls
from two_factor.admin import AdminSiteOTPRequired
from tenants.two_factor_overrides import AdminSetupView, admin_setup_complete
from integrations import views_retell
from integrations import views as integrations_views

# Fuerza OTP en /admin/
admin.site.__class__ = AdminSiteOTPRequired


# === HOME ===
def home_view(request):
    return render(request, "home/home.html")


# Admin login SIEMPRE -> 2FA + vuelve a /admin/
def admin_login_2fa(request):
    return redirect("/account/login/?next=/admin/")


urlpatterns = [
    # 2FA URLs (Login, Setup, QR, etc.)
    path("", include(tf_urls)),

    # Evita NoReverseMatch: two_factor usa reverse("home") como fallback
    #    Creamos el name="home" SIN chocar con tu path("home/", include("home.urls"))
    path("go-home/", RedirectView.as_view(url="/admin/", permanent=False), name="home"),

    # Admin: login siempre pasa por 2FA y vuelve al admin
    path("admin/login/", admin_login_2fa),

    # === ADMIN ===
    path("admin/", admin.site.urls),

    # === AUTENTICACIÓN / REGISTRO ===
    path("account/two_factor/setup/", AdminSetupView.as_view(), name="tf_setup_override"),
    path("account/two_factor/setup/complete/", admin_setup_complete, name="tf_setup_complete_override"),
    path("", tenant_login_view, name="login"),
    path("login/", tenant_login_view, name="login"),
    path("auth/login/", tenant_login_view, name="auth_login"),
    path("logout/", logout_view, name="logout"),
    path("auth/registro_cliente/", registro_cliente, name="auth_registro_cliente"),
    path("config/notificaciones/", views.config_notificaciones_view, name="config_notificaciones"),

    # === APLICACIONES PRINCIPALES ===
    path("dashboard/", include(("dashboard.urls", "dashboard"), namespace="dashboard")),
    path("rest/oauth2-credential/callback", views.oauth2_callback, name="oauth2_callback"),

    # Ingesta API / Integraciones
    path("inyeccion_api/", include(("inyeccion_api.urls", "inyeccion_api"), namespace="inyeccion_api")),

    # Dashboards SOAR
    path("dashboard-soar/", include(("soar_dashboard.urls", "soar_dashboard"), namespace="soar_dashboard")),
    path("soar/incidentes/", include(("soar_incidents.urls", "soar_incidents"), namespace="soar_incidents")),
    path("auth/cambiar_contraseña/", views.cambiar_contraseña, name="cambiar_contrasena"),

    # Reset contraseña
    path("auth/recuperar_contrasena/", accounts_views.recuperar_contrasena, name="recuperar_contrasena"),
    path("auth/reset/<uidb64>/<token>/", auth_views.PasswordResetConfirmView.as_view(
        template_name="auth/password_reset_confirm.html",
        success_url="/auth/reset/done/"
    ), name="password_reset_confirm"),
    path("auth/reset/done/", auth_views.PasswordResetCompleteView.as_view(
        template_name="auth/password_reset_complete.html"
    ), name="password_reset_complete"),

    # Portal
    path("home/", include("home.urls")),
    path("blacklist", home_views.blacklist_txt, name="blacklist_download_root_root"),
    path("siem/", include("siem.urls", namespace="siem")),
    path("", include("site24x7.urls")),
    path("soar/tickets/", include(("soar_tickets.urls", "soar_tickets"), namespace="soar_tickets")),

    # Retell call
    path("inntesec-agent/create-web-call/", views_retell.retell_create_web_call, name="retell_create_web_call"),
    path("inntesec-agent/get-call/<str:call_id>/", views_retell.retell_get_call, name="retell_get_call"),
    path("inntesec-agent/call/", integrations_views.retell_call_window, name="retell_call_window"),

    # Chat
    path("chat/", integrations_views.chat_window, name="chat_window"),
    path("chat/api/send/", integrations_views.chat_send_message, name="chat_send_message"),
]
