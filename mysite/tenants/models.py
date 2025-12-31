from django.db import models
from django.contrib.auth.models import AbstractUser
from django.conf import settings
from django.db.models.functions import Lower


# ======================================================
# MODELO BASE Tenant
# ======================================================
class Tenant(models.Model):
    name = models.CharField(max_length=255, unique=True, help_text="Nombre de la empresa (campo 'Empresa' de la API)")
    alarms_one_id = models.TextField(null=True, blank=True, help_text="ID de AlarmsOne")
    logs360siem_id = models.TextField(null=True, blank=True, help_text="ID de Logs360SIEM")
    site24x7_id = models.TextField(null=True, blank=True, help_text="ID de Site24x7")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


# ======================================================
# MODELO PROXY de la tabla externa telegram.solicitudes
# ======================================================
class Solicitud(models.Model):
    id = models.BigAutoField(primary_key=True)
    Chat_ID = models.BigIntegerField(db_column='Chat_ID')  # usa el nombre exacto de la columna

    class Meta:
        managed = False  # Django no intentará crear ni borrar esta tabla
        db_table = 'telegram.solicitudes'  # nombre exacto de la tabla externa

    def __str__(self):
        return f"Solicitud Telegram ({self.Chat_ID})"


# ======================================================
# CLIENTES (asociados a un Tenant)
# ======================================================
class Client(models.Model):
    id = models.IntegerField(
        primary_key=True,
        help_text="ID numérico del cliente proveniente del webhook (API externa)"
    )
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='clients', help_text="Empresa a la que pertenece el cliente")
    name = models.CharField(max_length=255, help_text="Nombre del cliente (campo 'Nombre' de la API)")
    email = models.EmailField(unique=True, help_text="Email del cliente (campo 'Email' de la API)")
    phone = models.CharField(max_length=50, null=True, blank=True, help_text="Teléfono del cliente (campo 'Telefono' de la API)")
    telegram_id = models.CharField(max_length=100, null=True, blank=True, help_text="ID de Telegram del cliente (campo 'Telegram' de la API)")

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='tenant_client_profile'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.tenant.name})"


# ======================================================
# USUARIOS por Tenant
# ======================================================
class TenantUser(AbstractUser):
    id = models.IntegerField(primary_key=True)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, null=True, blank=True, related_name='users')
    Alarma_Telefono = models.BooleanField(default=False)
    Alarma_Correo = models.BooleanField(default=False)
    Alarma_Telegram = models.BooleanField(default=False)
    hora_inicio = models.TimeField(null=True, blank=True)
    phone = models.CharField(max_length=50, null=True, blank=True, help_text="Teléfono del cliente (campo 'Telefono' de la API)")
    hora_fin = models.TimeField(null=True, blank=True)

    # Campo numérico para almacenar el Chat_ID de Telegram
    telegram_id = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        help_text="Identificador del chat de Telegram (texto o numérico)"
    )
    groups = None
    user_permissions = None

    def __str__(self):
        return f"{self.username} ({self.tenant.name if self.tenant else 'Sin tenant'})"


class TenantDashboardEmbed(models.Model):
    """
    Guarda URLs de iframes externos asociados a un Tenant.
    """
    tenant = models.OneToOneField(
        Tenant,
        on_delete=models.CASCADE,
        related_name="dashboard_iframe",
        help_text="Empresa a la que pertenece este iframe"
    )

    tenant_name = models.CharField(
      max_length=255,
      editable=False,
      blank=True,
      default="",
      help_text="Nombre del tenant en el momento de guardar el registro"
    )

    iframe_url = models.URLField(
        help_text="URL pública del dashboard a embeber en un iframe"
    )

    # ✅ NUEVAS COLUMNAS (urls adicionales por módulo)
    threat_analytics = models.TextField(blank=True, null=True)
    microsoft365 = models.TextField(blank=True, null=True)
    
    networks = models.TextField(blank=True, null=True)
    eventos_diarios = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Site 24x7 Iframe"
        verbose_name_plural = "Site 24x7 Iframe"

    def save(self, *args, **kwargs):
        if self.tenant_id and getattr(self.tenant, "name", None):
            self.tenant_name = self.tenant.name
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.tenant_name or getattr(self.tenant, 'name', '')} - Dashboard"

def default_severity():
    """
    Estructura por defecto para las severidades.
    Puedes ajustarla a lo que necesites.
    """
    return {
        "baja": True,
        "media": True,
        "alta": True,
        "critica": True,
    }


class NotificationChannelPreference(models.Model):
    """
    Preferencias de severidad por canal de notificación.

    - user: OneToOne => user_id único en la tabla.
    - telefono / correo / telegram: se guardan como JSON
      con las severidades marcadas (baja, media, alta, critica).
    """
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notification_pref",
    )

    telefono = models.JSONField(default=default_severity)
    correo = models.JSONField(default=default_severity)
    telegram = models.JSONField(default=default_severity)

    def __str__(self):
        return f"Preferencias de notificación de {self.user}"

    class Meta:
        # Tabla REAL en Postgres
        db_table = 'agent"."tenants_notificationchannelpreference'
        # Muy importante: que Django NO toque esta tabla
        managed = False