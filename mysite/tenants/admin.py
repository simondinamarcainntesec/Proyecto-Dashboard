from django import forms
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.db.models.functions import Lower
from django.utils import timezone

from .models import Tenant, Client, TenantUser
from .models import TenantDashboardEmbed
from .models import NotificationChannelPreference

from home.models import TenantCredentials

# Mover modelos de home al app "tenants" en el admin
TenantCredentials._meta.app_label = "tenants"
TenantDashboardEmbed._meta.app_label = "tenants"


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
        "id",
        "username", "email", "first_name", "last_name",
        "tenant", "is_active", "is_staff", "is_superuser", "last_login",
        "Alarma_Telegram", "Alarma_Telefono", "Alarma_Correo",
        "phone",
    )

    list_filter = ("tenant", "is_staff", "is_superuser", "is_active")
    search_fields = ("username", "email", "first_name", "last_name", "phone")
    ordering = ("username",)

    filter_horizontal = ()
    autocomplete_fields = ("tenant",)
    exclude = ("groups", "user_permissions",)
    readonly_fields = ("_groups_readonly", "_perms_readonly", "last_login", "date_joined")

    fieldsets = (
        (None, {"fields": ("username", "password")}),
        ("Información personal", {"fields": ("first_name", "last_name", "email", "phone")}),  # phone editable
        ("Tenant", {"fields": ("tenant",)}),

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
                "id",
                "username", "email", "phone",  # phone al crear
                "password1", "password2",
                "tenant", "is_active", "is_staff", "is_superuser",
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


@admin.register(TenantDashboardEmbed)
class TenantDashboardEmbedAdmin(admin.ModelAdmin):
    """
    Admin para el modelo que guarda el iframe por tenant.
    Muestra el nombre del tenant y el tenant_name cacheado.
    """
    list_display = ("tenant", "tenant_name", "iframe_url", "created_at", "updated_at")
    search_fields = ("tenant_name", "tenant__name", "iframe_url")
    list_filter = ("tenant", "created_at", "updated_at")
    ordering = ("tenant_name",)
    list_select_related = ("tenant",)

    readonly_fields = ("tenant_name", "created_at", "updated_at")

    fieldsets = (
        ("Tenant", {"fields": ("tenant", "tenant_name")}),
        ("Dashboard embebido", {"fields": ("iframe_url",)}),
        ("Timestamps", {
            "classes": ("collapse",),
            "fields": ("created_at", "updated_at"),
        }),
    )


@admin.register(TenantCredentials)
class TenantCredentialsAdmin(admin.ModelAdmin):
    list_display = (
        "tenant_id",
        "tenant_name",
        "username",
        "is_active",
        "alarms_one_id",
        "logs360siem_id",
        "site24x7_id",
        "first_login_at",
        "last_login_at",
        "created_at",
        "updated_at",
    )

    search_fields = (
        "tenant_name",
        "username",
        "alarms_one_id",
        "logs360siem_id",
        "site24x7_id",
        "password",
    )

    list_filter = ("is_active", "tenant_id", "created_at", "updated_at")
    ordering = ("-updated_at",)

    readonly_fields = ("first_login_at", "last_login_at", "created_at", "updated_at")

    fieldsets = (
        ("Identificación del Tenant", {"fields": ("tenant_id", "tenant_name")}),
        ("Servicios habilitados", {"fields": ("alarms_one_id", "logs360siem_id", "site24x7_id")}),
        ("Credenciales de acceso", {"fields": ("username", "password", "is_active")}),
        ("Timestamps", {
            "classes": ("collapse",),
            "fields": ("first_login_at", "last_login_at", "created_at", "updated_at"),
        }),
    )


# =========================
# NotificationChannelPreference (Checkboxes + sin campos extra)
# =========================

SEVERITY_CHOICES = (
    ("baja", "Baja"),
    ("media", "Media"),
    ("alta", "Alta"),
    ("critica", "Crítica"),
)


class NotificationChannelPreferenceAdminForm(forms.ModelForm):
    # Reemplazamos JSONField por checkboxes (lista) y lo convertimos a dict en clean_*
    telefono = forms.MultipleChoiceField(
        choices=SEVERITY_CHOICES,
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label="Teléfono",
    )
    correo = forms.MultipleChoiceField(
        choices=SEVERITY_CHOICES,
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label="Correo",
    )
    telegram = forms.MultipleChoiceField(
        choices=SEVERITY_CHOICES,
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label="Telegram",
    )

    class Meta:
        model = NotificationChannelPreference
        fields = ("user", "telefono", "correo", "telegram")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Dropdown user: "Nombre (Tenant) — correo/username" (SIN ID)
        uf = self.fields.get("user")
        if uf:
            uf.queryset = TenantUser.objects.select_related("tenant").all()

            def _label(u: TenantUser):
                tenant_name = getattr(getattr(u, "tenant", None), "name", "—")
                full = (u.get_full_name() or "").strip()
                name = full or (getattr(u, "first_name", "") or "").strip() or getattr(u, "username", "—")
                username = getattr(u, "username", "—")  # en tu caso suele ser correo
                return f"{name} ({tenant_name}) — {username}"

            uf.label_from_instance = _label

        # Iniciales desde dict JSON -> lista checkeada
        inst = getattr(self, "instance", None)
        if inst and getattr(inst, "pk", None):
            self.initial["telefono"] = [k for k, _ in SEVERITY_CHOICES if (inst.telefono or {}).get(k) is True]
            self.initial["correo"] = [k for k, _ in SEVERITY_CHOICES if (inst.correo or {}).get(k) is True]
            self.initial["telegram"] = [k for k, _ in SEVERITY_CHOICES if (inst.telegram or {}).get(k) is True]

    def _dict_from_selected(self, selected_list):
        selected = set(selected_list or [])
        return {k: (k in selected) for k, _ in SEVERITY_CHOICES}

    def clean_telefono(self):
        return self._dict_from_selected(self.cleaned_data.get("telefono"))

    def clean_correo(self):
        return self._dict_from_selected(self.cleaned_data.get("correo"))

    def clean_telegram(self):
        return self._dict_from_selected(self.cleaned_data.get("telegram"))


@admin.register(NotificationChannelPreference)
class NotificationChannelPreferenceAdmin(admin.ModelAdmin):
    form = NotificationChannelPreferenceAdminForm
    list_select_related = ("user", "user__tenant")

    # tabla: Usuario + severidades activas por canal
    list_display = ("user_display", "telefono_levels", "correo_levels", "telegram_levels")
    list_display_links = ("user_display",)

    search_fields = (
        "user__username",
        "user__email",
        "user__first_name",
        "user__last_name",
        "user__tenant__name",
    )
    list_filter = ("user__tenant",)

    # “barras/títulos” por canal (como en tus otros módulos)
    fieldsets = (
        ("Usuario", {"fields": ("user",)}),
        ("Teléfono", {"fields": ("telefono",)}),
        ("Correo", {"fields": ("correo",)}),
        ("Telegram", {"fields": ("telegram",)}),
    )

    # al editar: user bloqueado (evita mover prefs a otro user)
    def get_readonly_fields(self, request, obj=None):
        return ("user",) if obj else ()

    # --- helpers list display ---
    def user_display(self, obj):
        u = getattr(obj, "user", None)
        if not u:
            return "—"
        tenant_name = getattr(getattr(u, "tenant", None), "name", "—")
        full = (u.get_full_name() or u.username or "—").strip()
        return f"{full} ({tenant_name})"
    user_display.short_description = "Usuario"

    def _levels_str(self, data):
        """
        data: dict JSON como {"baja": True/False, "media": ..., "alta": ..., "critica": ...}
        Devuelve: "Baja, Media" o "—"
        """
        data = data or {}
        labels = []
        for key, label in SEVERITY_CHOICES:
            if data.get(key) is True:
                labels.append(label)
        return ", ".join(labels) if labels else "—"

    def telefono_levels(self, obj):
        return self._levels_str(getattr(obj, "telefono", None))
    telefono_levels.short_description = "Teléfono"

    def correo_levels(self, obj):
        return self._levels_str(getattr(obj, "correo", None))
    correo_levels.short_description = "Correo"

    def telegram_levels(self, obj):
        return self._levels_str(getattr(obj, "telegram", None))
    telegram_levels.short_description = "Telegram"
