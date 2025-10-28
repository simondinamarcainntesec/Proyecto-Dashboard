from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import render
from tenants import views
from tenants.views import tenant_login_view, logout_view


def home_view(request):
    return render(request, 'home/home.html')
urlpatterns = [
      path("admin/", admin.site.urls),

        # === LOGIN / LOGOUT ===
        path("login/", tenant_login_view, name="login"),        # ← nombre oficial
        path("auth/login/", tenant_login_view, name="auth_login"),  # ← alias opcional
        path("logout/", logout_view, name="logout"),

        path("", login_required(home_view, login_url="login"), name="home"),
        path("inyeccion_api/", include(("inyeccion_api.urls", "inyeccion_api"), namespace="inyeccion_api")),
        path("dashboard/", include("dashboard.urls")),
        path("integrations/", include("integrations.urls")),
    
]
