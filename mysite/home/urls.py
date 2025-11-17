from django.urls import path
from .views import home_index, blacklist_create_ticket, whitelist_create_ticket

app_name = "home"

urlpatterns = [
    path("", home_index, name="index"),
    path("blacklist/create-ticket/", blacklist_create_ticket, name="blacklist_create_ticket"),
    path("whitelist/create-ticket/", whitelist_create_ticket, name="whitelist_create_ticket"),
]
