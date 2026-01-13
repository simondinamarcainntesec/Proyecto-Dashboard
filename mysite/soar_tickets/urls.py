from django.urls import path
from .views import (
    tickets_list,
    ticket_close,
    ticket_update_due_date,   # ✅ NUEVO
    api_tenant_users,
    api_ticket_create,
)

app_name = "soar_tickets"

urlpatterns = [
    path("", tickets_list, name="list"),
    path("close/<int:ticket_id>/", ticket_close, name="close"),

    # ✅ NUEVO: actualizar fecha de vencimiento (solo creador)
    path("due/<int:ticket_id>/", ticket_update_due_date, name="due"),

    # APIs
    path("api/tenant-users/", api_tenant_users, name="api_tenant_users"),
    path("api/tickets/create/", api_ticket_create, name="api_ticket_create"),
]
