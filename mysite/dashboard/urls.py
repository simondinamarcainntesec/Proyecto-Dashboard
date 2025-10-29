from django.urls import path
from .views import dashboard_view
from . import realtime

urlpatterns = [
    path('alarmsone/', dashboard_view, name='dashboard_alarmsone'),
    path('realtime/', realtime.realtime_page, name='dashboard_realtime'),
]