from django.urls import path
from .views import (
    tickets_list,
    ticket_close,
    api_tenant_users,
    api_ticket_create,
)

app_name = "soar_tickets"

urlpatterns = [
    path("", tickets_list, name="list"),
    path("close/<int:ticket_id>/", ticket_close, name="close"),

    # APIs
    path("api/tenant-users/", api_tenant_users, name="api_tenant_users"),
    path("api/tickets/create/", api_ticket_create, name="api_ticket_create"),
]
