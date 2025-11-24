from django.db import models

# Create your models here.
# home/models.py
from django.db import models

class TelegramSolicitud(models.Model):
    id = models.IntegerField(primary_key=True, db_column='id')
    chat_id = models.CharField(max_length=255, db_column='Chat_ID', blank=True, null=True)
    nombre = models.CharField(max_length=255, db_column='Nombre', blank=True, null=True)
    correo = models.CharField(max_length=255, db_column='Correo', blank=True, null=True)
    empresa = models.CharField(max_length=255, db_column='Empresa', blank=True, null=True)
    solicitud = models.TextField(db_column='Solicitud', blank=True, null=True)
    fecha_solicitud = models.DateTimeField(db_column='Fecha_Solicitud', blank=True, null=True)

    class Meta:
        managed = False  # ← no crear/alterar tabla
        db_table = 'telegram"."solicitudes'  # ← schema.tabla (mismo patrón que usas con agent"."ia_soar)
        ordering = ['-fecha_solicitud']

    def __str__(self):
        return f"{self.nombre or 'N/A'} • {self.fecha_solicitud or ''}"

class IPBlacklist(models.Model):
    ip = models.CharField(
        max_length=255,
        primary_key=True,   # asumo que cada IP es única en la tabla
    )
    pais = models.CharField(
        max_length=255,
        null=True,
        blank=True,
    )
    fecha_creacion = models.DateTimeField(
        null=True,
        blank=True,
    )
    fecha_actualizacion = models.DateTimeField(
        null=True,
        blank=True,
    )
    logid = models.TextField(
        null=True,
        blank=True,
    )
    # Nombre Python "log_description", columna real "log_descripcion"
    log_description = models.TextField(
        db_column="log_descripcion",
        null=True,
        blank=True,
    )
    mensaje = models.TextField(
        null=True,
        blank=True,
    )
    usuario = models.TextField(
        null=True,
        blank=True,
    )
    dispositivo = models.TextField(
        null=True,
        blank=True,
    )

    class Meta:
        managed = False  # la tabla ya existe en PostgreSQL
        db_table = 'agent"."ip_blacklist'
        verbose_name = "IP en blacklist"
        verbose_name_plural = "IPs en blacklist"

    def __str__(self) -> str:
        return self.ip


class IPWhitelist(models.Model):
    ip = models.CharField("IP", max_length=255, primary_key=True)
    pais = models.CharField(max_length=255, null=True, blank=True)
    fecha_creacion = models.DateTimeField(null=True, blank=True)
    fecha_actualizacion = models.DateTimeField(null=True, blank=True)
    region = models.TextField(null=True, blank=True)
    ciudad = models.TextField(null=True, blank=True)
    isp = models.TextField(null=True, blank=True)
    organizacion = models.TextField(null=True, blank=True)   # ← aquí guardaremos el tenant
    cliente = models.TextField(null=True, blank=True)        # ← aquí el usuario/correo
    mobile = models.TextField(null=True, blank=True)
    tenant_id = models.IntegerField(null=True, blank=True)

    # NUEVO
    motivo = models.TextField(null=True, blank=True)

    class Meta:
        managed = False
        # Forma segura para referenciar esquema + tabla
        db_table = 'agent"."ip_whitelist'
        verbose_name = "IP Whitelist"
        verbose_name_plural = "IP Whitelist"

    def __str__(self):
        return self.ip

# home/models_credentials.py  (o dentro de tu app "home/models.py")
from django.db import models


class TenantCredentials(models.Model):
    """
    Mapea la tabla agent.tenant_credentials (PostgreSQL, esquema 'agent').
    Un registro por tenant (tenant_id = PK). No gestionado por Django.
    """
    tenant_id = models.IntegerField(primary_key=True)
    tenant_name = models.TextField(unique=True)

    # IDs de servicios (texto tal como vienen desde tu tabla tenants)
    alarms_one_id = models.TextField(blank=True, null=True)
    logs360siem_id = models.TextField(blank=True, null=True)
    site24x7_id = models.TextField(blank=True, null=True)

    # Credenciales compartidas por tenant
    username = models.TextField()
    password = models.TextField()

    # Estado y auditoría mínima
    is_active = models.BooleanField(default=True)
    first_login_at = models.DateTimeField(blank=True, null=True)
    last_login_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'agent"."tenant_credentials'  # <-- importante para esquema
        verbose_name = "Tenant credentials"
        verbose_name_plural = "Tenant credentials"

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.tenant_name} (tenant_id={self.tenant_id})"

    @property
    def masked_password(self) -> str:
        """Útil si quieres mostrar sin exponer completa en logs/UI."""
        if not self.password:
            return ""
        if len(self.password) <= 4:
            return "•" * len(self.password)
        return self.password[:2] + "•" * (len(self.password) - 4) + self.password[-2:]

    @classmethod
    def get_active_for_tenant(cls, tenant_id: int) -> "TenantCredentials | None":
        try:
            return cls.objects.get(tenant_id=tenant_id, is_active=True)
        except cls.DoesNotExist:
            return None
