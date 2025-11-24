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

    # Descarga con Basic Auth (URL que muestras en el modal)

    # Página final que entrega el TXT (después del Basic Auth)
    path("blacklist/page/", views.blacklist_download_page, name="blacklist_download_page"),

    # Endpoint TXT “puro” (si aún lo usas para robots/scripts)
    path("blacklist.txt", views.blacklist_txt, name="blacklist_txt"),
    path("blacklist", home_views.blacklist_txt, name="blacklist_download_root"),
    path("home_prueba_inntesec/blacklist/page/", views.blacklist_download_page, name="blacklist_download_page"),
]