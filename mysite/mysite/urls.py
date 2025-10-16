from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse

def home_view(request):
    return HttpResponse("Home. <a href='/dashboard/'>Dashboard</a>")

urlpatterns = [
    path("admin/", admin.site.urls),
    path("login/",  auth_views.LoginView.as_view(template_name="auth/login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("", login_required(home_view), name="home"),
    path("dashboard/", include(("dashboard.urls", "dashboard"), namespace="dashboard")),
]
