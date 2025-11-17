from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.db.models.functions import Lower
from django.utils.html import format_html

from .models import Tenant, Client, TenantUser
from django.utils import timezone

@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ("name", "alarms_one_id", "logs360siem_id", "site24x7_id", "created_at")
    search_fields = ("name", "alarms_one_id", "logs360siem_id", "site24x7_id")
    list_filter = ("created_at",)
    ordering = ("name",)



@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "tenant", "id", "phone", "telegram_id", "user")
    list_filter = ("tenant",)
    search_fields = ("name", "email", "phone", "telegram_id", "id")
    autocomplete_fields = ("tenant", "user")

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(_name_lower=Lower("name")).order_by("_name_lower")



@admin.register(TenantUser)
class TenantUserAdmin(UserAdmin):
    """
    Admin de TenantUser con campos de alarmas editables,
    y sin dependencias a grupos/permisos para evitar errores.
    """
    model = TenantUser

    list_display = (
        "username", "email", "first_name", "last_name",
        "tenant", "is_active", "is_staff", "is_superuser", "last_login",
        "Alarma_Telegram", "Alarma_Telefono", "Alarma_Correo",
    )

    list_filter = ("tenant", "is_staff", "is_superuser", "is_active")
    search_fields = ("username", "email", "first_name", "last_name")
    ordering = ("username",)

    filter_horizontal = ()
    autocomplete_fields = ("tenant",)
    exclude = ("groups", "user_permissions",)
    readonly_fields = ("_groups_readonly", "_perms_readonly", "last_login", "date_joined")

    fieldsets = (
        (None, {"fields": ("username", "password")}),
        ("Información personal", {"fields": ("first_name", "last_name", "email")}),
        ("Tenant", {"fields": ("tenant",)}),

        # 🔔 Campos de alarmas
        ("Notificaciones y Alarmas", {
            "fields": ("Alarma_Telegram", "Alarma_Telefono", "Alarma_Correo"),
        }),

        ("Permisos", {
            "fields": ("is_active", "is_staff", "is_superuser", "_groups_readonly", "_perms_readonly"),
        }),
        ("Fechas importantes", {"fields": ("last_login", "date_joined")}),
    )

    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": (
                "username", "email", "password1", "password2",
                "tenant", "is_active", "is_staff", "is_superuser",
                # 🔔 También disponibles al crear
                "Alarma_Telegram", "Alarma_Telefono", "Alarma_Correo",
            ),
        }),
    )

    # --------- helpers readonly ---------
    def _groups_readonly(self, obj):
        try:
            names = list(obj.groups.values_list("name", flat=True))
        except Exception:
            return "—"
        return ", ".join(sorted(names)) if names else "—"
    _groups_readonly.short_description = "Grupos"

    def _perms_readonly(self, obj):
        try:
            perms = list(obj.user_permissions.values_list("codename", flat=True))
        except Exception:
            return "—"
        if not perms:
            return "—"
        preview = ", ".join(sorted(perms[:20]))
        if len(perms) > 20:
            preview += f" … (+{len(perms) - 20})"
        return preview
    _perms_readonly.short_description = "Permisos (codenames)"

    def save_model(self, request, obj, form, change):
        """Sincroniza automáticamente con Client al guardar."""
        super().save_model(request, obj, form, change)
        from tenants.models import Client
        if obj.email and obj.tenant:
            client, created = Client.objects.update_or_create(
                id=obj.id,
                defaults={
                    "name": obj.first_name or obj.username,
                    "email": obj.email,
                    "tenant": obj.tenant,
                    "user": obj,
                    "updated_at": timezone.now(),
                },
            )
            if created:
                client.created_at = timezone.now()
                client.save(update_fields=["created_at"])
                print(f"🟢 Cliente creado: {client.email}")
            else:
                print(f"🟡 Cliente actualizado: {client.email}")

    def save_related(self, request, form, formsets, change):
        # No tocamos relaciones M2M
        pass