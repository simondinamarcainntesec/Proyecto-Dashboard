from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import render
from tenants import views
from tenants.views import tenant_login_view, logout_view
from accounts.views import registro_cliente

def home_view(request):
    return render(request, 'home/home.html')

urlpatterns = [
    path("admin/", admin.site.urls),

    # === LOGIN / LOGOUT ===
    path("", tenant_login_view, name="login"),
    path("auth/login/", tenant_login_view, name="auth_login"),
    path("logout/", logout_view, name="logout"),
    path("auth/registro_cliente/", registro_cliente, name="auth/registro_cliente"),

    # === APLICACIONES ===
    path("inyeccion_api/", include(("inyeccion_api.urls", "inyeccion_api"), namespace="inyeccion_api")),
    path('dashboard/', include('dashboard.urls')),   # 👈 agregué la coma
    path("integrations/", include("integrations.urls")),
    path("dashboard-soar/", include("soar_dashboard.urls")),
]
