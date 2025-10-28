from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import render
from tenants import views
from tenants.views import tenant_login_view

def home_view(request):
    return render(request, 'home/home.html')
urlpatterns = [
    path('admin/', admin.site.urls),
    path('login/', tenant_login_view, name='tenant_login'),
    path('auth/login/', views.tenant_login_view, name='tenant_login'),
    path("", login_required(home_view), name="home"),
    path("inyeccion_api/", include(("inyeccion_api.urls", "inyeccion_api"), namespace="inyeccion_api")),
    path("dashboard/", include("dashboard.urls")),
    path("integrations/", include("integrations.urls")),
    
]
