# home/urls.py
from django.urls import path
from . import views
from home import views as home_views

app_name = "home"

urlpatterns = [
    # Home
    path("", views.home_index, name="index"),

    # Tickets Blacklist / Whitelist
    path("blacklist/create-ticket/", views.blacklist_create_ticket, name="blacklist_create_ticket"),
    path("whitelist/create-ticket/", views.whitelist_create_ticket, name="whitelist_create_ticket"),

    # Descarga con Basic Auth
    path("blacklist/page/", views.blacklist_download_page, name="blacklist_download_page"),

    # Endpoint TXT “puro”
    path("blacklist.txt", views.blacklist_txt, name="blacklist_txt"),
    path("blacklist", home_views.blacklist_txt, name="blacklist_download_root"),
    path("home/blacklist/page/", views.blacklist_download_page, name="blacklist_download_page"),

    # Config notificaciones
    path("config/notificaciones/", views.config_notificaciones, name="config_notificaciones"),

    # Whitelist: preferencias países (POR TENANT)
    path(
        "whitelist/get-countries/",
        views.whitelist_get_countries,
        name="whitelist_get_countries",
    ),
    path(
        "whitelist/save-countries/",
        views.whitelist_save_countries,
        name="whitelist_save_countries",
    ),
]
