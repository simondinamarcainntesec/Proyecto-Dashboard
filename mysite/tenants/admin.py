from django import forms
from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth import get_user_model
from django.db.models.functions import Lower
from django.utils import timezone
from django.db import transaction

from .models import Tenant, Client, TenantUser
from .models import TenantDashboardEmbed
from .models import NotificationChannelPreference
from .models import Tenants_contracts  # ✅ admin contratos

from home.models import TenantCredentials

# Mover modelos de home al app "tenants" en el admin
TenantCredentials._meta.app_label = "tenants"
TenantDashboardEmbed._meta.app_label = "tenants"

User = get_user_model()  # TenantUser


# =========================================================
# TENANT
# =========================================================
@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active", "alarms_one_id", "logs360siem_id", "site24x7_id", "created_at")
    search_fields = ("name", "alarms_one_id", "logs360siem_id", "site24x7_id")
    list_filter = ("is_active", "created_at")
    ordering = ("name",)
    # Nota: ya no hacemos el toggle masivo acá, porque ahora "manda contratos".


# =========================================================
# CLIENT
# =========================================================
@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "tenant", "id", "phone", "telegram_id", "user")
    list_filter = ("tenant",)
    search_fields = ("name", "email", "phone", "telegram_id", "id")
    autocomplete_fields = ("tenant", "user")

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(_name_lower=Lower("name")).order_by("_name_lower")


# =========================================================
# TENANT USER (con blindaje)
# =========================================================
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
        ("Información personal", {"fields": ("first_name", "last_name", "email", "phone")}),
        ("Tenant", {"fields": ("tenant",)}),

        ("Notificaciones y Alarmas", {
            "fields": ("Alarma_Telegram", "Alarma_Telefono", "Alarma_Correo"),
        }),

        ("Permisos", {
            "fields": ("is_active", "is_staff", "is_superuser", "_groups_readonly", "_perms_readonly"),
        }),
        ("Fechas importantes", {"fields": ("last_login", "date_joined")}),
    )

    # ✅ corregido (sin la línea rara)
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": (
                "id",
                "username", "email", "phone",
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
        """
        Blindaje:
        - Si el tenant está desactivado, este usuario NO puede quedar activo.
        Además, sincroniza automáticamente con Client al guardar.
        """
        tenant = getattr(obj, "tenant", None)
        if tenant and getattr(tenant, "is_active", True) is False:
            if obj.is_active:
                messages.warning(
                    request,
                    f"El tenant '{tenant.name}' está desactivado: se fuerza este usuario a inactivo."
                )
            obj.is_active = False

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
        pass


# =========================================================
# DASHBOARD EMBEDS
# =========================================================
@admin.register(TenantDashboardEmbed)
class TenantDashboardEmbedAdmin(admin.ModelAdmin):
    list_display = (
        "tenant",
        "tenant_name",
        "iframe_url",
        "threat_analytics",
        "microsoft365",
        "networks",
        "eventos_diarios",
        "created_at",
        "updated_at",
    )

    search_fields = (
        "tenant_name",
        "tenant__name",
        "iframe_url",
        "threat_analytics",
        "microsoft365",
        "networks",
        "eventos_diarios",
    )

    list_filter = ("tenant", "created_at", "updated_at")
    ordering = ("tenant_name",)
    list_select_related = ("tenant",)
    readonly_fields = ("tenant_name", "created_at", "updated_at")

    fieldsets = (
        ("Tenant", {"fields": ("tenant", "tenant_name")}),
        ("Dashboards / Embeds", {
            "fields": (
                "iframe_url",
                "threat_analytics",
                "microsoft365",
                "networks",
                "eventos_diarios",
            )
        }),
        ("Timestamps", {
            "classes": ("collapse",),
            "fields": ("created_at", "updated_at"),
        }),
    )


# =========================================================
# TENANT CREDENTIALS (HOME)
# =========================================================
class TenantCredentialsAdminForm(forms.ModelForm):
    class Meta:
        model = TenantCredentials
        fields = (
            "tenant_id",
            "tenant_name",
            "alarms_one_id",
            "logs360siem_id",
            "site24x7_id",
            "username",
            "password",
            "is_active",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        inst = getattr(self, "instance", None)
        if inst and getattr(inst, "pk", None):
            self.initial["username"] = inst.username_plain
            self.initial["password"] = inst.password_plain

        pwd_field = self.fields.get("password")
        if pwd_field:
            pwd_field.widget = forms.PasswordInput(render_value=True)


@admin.register(TenantCredentials)
class TenantCredentialsAdmin(admin.ModelAdmin):
    form = TenantCredentialsAdminForm
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


# =========================================================
# CONTRACTS ADMIN (MANDA ACTIVACIÓN) - CORREGIDO CON PRIORIDAD
# =========================================================
MANDATORY_CONTRACT_NAMES = {"POC Inntesec Agent", "Inntesec Agent"}
STATUS_CHOICES = (
    ("Active", "Active"),
    ("Expired", "Expired"),
)

# prioridad: si existe Inntesec Agent, manda ese; si no, manda POC
CONTRACT_PRIORITY = ["Inntesec Agent", "POC Inntesec Agent"]


class TenantsContractsAdminForm(forms.ModelForm):
    status = forms.ChoiceField(choices=STATUS_CHOICES, required=True, label="Status")

    class Meta:
        model = Tenants_contracts
        fields = "__all__"


@admin.register(Tenants_contracts)
class TenantsContractsAdmin(admin.ModelAdmin):
    form = TenantsContractsAdminForm

    list_display = ("contract_id", "tenant_id", "contract_name", "status", "start_date", "expiry_date", "account")
    list_filter = ("status", "contract_name", "start_date", "expiry_date")
    search_fields = ("contract_id", "contract_name", "account", "tenant_id")
    ordering = ("-expiry_date",)

    def _normalize_status(self, s: str) -> str:
        return (s or "").strip()

    def _pick_effective_contract(self, tenant_id: int):
        """
        Devuelve el contrato que MANDA por prioridad:
        - Inntesec Agent (si existe)
        - si no, POC Inntesec Agent
        Si hay múltiples por nombre, toma el de mayor expiry_date.
        """
        for name in CONTRACT_PRIORITY:
            row = (
                Tenants_contracts.objects
                .filter(tenant_id=tenant_id, contract_name=name)
                .order_by("-expiry_date")
                .first()
            )
            if row:
                return row
        return None

    @transaction.atomic
    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)

        # Solo aplicamos regla si el contrato editado es de los mandatorios
        if (obj.contract_name or "").strip() not in MANDATORY_CONTRACT_NAMES:
            messages.info(request, f"Contrato guardado (no mandatorio): '{obj.contract_name}'. No se aplicó activación.")
            return

        # Elegir el contrato efectivo (manda por prioridad)
        effective = self._pick_effective_contract(obj.tenant_id)
        if not effective:
            messages.warning(request, f"No se encontró contrato efectivo para tenant_id={obj.tenant_id}. No se aplicó activación.")
            return

        eff_status = self._normalize_status(getattr(effective, "status", ""))
        if eff_status not in {"Active", "Expired"}:
            messages.info(request, f"Status '{eff_status}' guardado en contrato efectivo. (No se aplicó regla).")
            return

        tenant = Tenant.objects.select_for_update().filter(id=obj.tenant_id).first()
        if not tenant:
            messages.error(request, f"No existe Tenant con id={obj.tenant_id}. No se pudo sincronizar activación.")
            return

        qs_users = User.objects.filter(tenant=tenant).exclude(is_superuser=True)

        desired_active = (eff_status == "Active")

        # siempre dejamos consistente: tenant + TODOS sus users
        tenant.is_active = desired_active
        tenant.save(update_fields=["is_active"])

        updated = qs_users.update(is_active=desired_active)

        if desired_active:
            messages.success(
                request,
                f"Contrato efectivo: '{effective.contract_name}' = Active → Tenant '{tenant.name}' activado + {updated} usuario(s) activado(s)."
            )
        else:
            messages.warning(
                request,
                f"Contrato efectivo: '{effective.contract_name}' = Expired → Tenant '{tenant.name}' desactivado + {updated} usuario(s) desactivado(s)."
            )


# =========================================================
# NotificationChannelPreference (Checkboxes + sin campos extra)
# =========================================================
SEVERITY_CHOICES = (
    ("baja", "Baja"),
    ("media", "Media"),
    ("alta", "Alta"),
    ("critica", "Crítica"),
)

class NotificationChannelPreferenceAdminForm(forms.ModelForm):
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

        uf = self.fields.get("user")
        if uf:
            uf.queryset = TenantUser.objects.select_related("tenant").all()

            def _label(u: TenantUser):
                tenant_name = getattr(getattr(u, "tenant", None), "name", "—")
                full = (u.get_full_name() or "").strip()
                name = full or (getattr(u, "first_name", "") or "").strip() or getattr(u, "username", "—")
                username = getattr(u, "username", "—")
                return f"{name} ({tenant_name}) — {username}"

            uf.label_from_instance = _label

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

    fieldsets = (
        ("Usuario", {"fields": ("user",)}),
        ("Teléfono", {"fields": ("telefono",)}),
        ("Correo", {"fields": ("correo",)}),
        ("Telegram", {"fields": ("telegram",)}),
    )

    def get_readonly_fields(self, request, obj=None):
        return ("user",) if obj else ()

    def user_display(self, obj):
        u = getattr(obj, "user", None)
        if not u:
            return "—"
        tenant_name = getattr(getattr(u, "tenant", None), "name", "—")
        full = (u.get_full_name() or u.username or "—").strip()
        return f"{full} ({tenant_name})"
    user_display.short_description = "Usuario"

    def _levels_str(self, data):
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
