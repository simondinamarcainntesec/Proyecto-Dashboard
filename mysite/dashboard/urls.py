from django.urls import path
from .views import dashboard_view
from . import realtime

urlpatterns = [
    path("", dashboard_view, name="dashboard_home"),
    path("realtime/", realtime.realtime_page, name="dashboard_realtime"),


]
    

