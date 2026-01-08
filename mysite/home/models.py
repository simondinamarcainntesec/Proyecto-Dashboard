import base64
import hashlib
import logging
import os

from cryptography.fernet import Fernet, InvalidToken
from django.db import models
from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from tenants.models import Tenant

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Cifrado simétrico para credenciales de tenant
# ---------------------------------------------------------------------------
_cipher_instance: Fernet | None = None


def _build_cipher() -> Fernet:
    """
    Construye un cifrador Fernet a partir de una key estable.
    - Usa settings.CREDENTIALS_ENCRYPTION_KEY o env CREDENTIALS_ENCRYPTION_KEY si existe.
    - Fallback: settings.SECRET_KEY (derivado vía SHA-256 para tamaño adecuado).
    """
    raw_key = (
        getattr(settings, "CREDENTIALS_ENCRYPTION_KEY", None)
        or os.getenv("CREDENTIALS_ENCRYPTION_KEY")
        or settings.SECRET_KEY
    )

    raw_str = str(raw_key or "")
    digest = hashlib.sha256(raw_str.encode("utf-8")).digest()
    key = base64.urlsafe_b64encode(digest)
    return Fernet(key)


def _get_cipher() -> Fernet:
    global _cipher_instance
    if _cipher_instance is None:
        _cipher_instance = _build_cipher()
    return _cipher_instance


def _is_probably_encrypted(value: str) -> bool:
    """Heurística simple para evitar doble cifrado (tokens Fernet empiezan con gAAAA)."""
    return isinstance(value, str) and value.startswith("gAAAA") and len(value) > 40


def _encrypt_value(value: str | None) -> str:
    if value is None:
        return ""
    s = str(value)
    if not s:
        return ""
    try:
        token = _get_cipher().encrypt(s.encode("utf-8"))
        return token.decode("utf-8")
    except Exception:
        logger.exception("[CRED] Error cifrando valor")
        return s


def _decrypt_value(value: str | None) -> str:
    if value is None:
        return ""
    s = str(value)
    if not s:
        return ""
    try:
        return _get_cipher().decrypt(s.encode("utf-8")).decode("utf-8")
    except InvalidToken:
        # No estaba cifrado; devolver tal cual para compatibilidad retro
        return s
    except Exception:
        logger.exception("[CRED] Error descifrando valor")
        return s


def _encrypt_if_needed(value: str | None) -> str:
    if value is None:
        return ""
    s = str(value)
    if not s:
        return ""
    if _is_probably_encrypted(s):
        return s
    return _encrypt_value(s)


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
        db_table = 'telegram"."solicitudes'  # ← schema.tabla
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
        db_table = 'agent"."ip_whitelist'
        verbose_name = "IP Whitelist"
        verbose_name_plural = "IP Whitelist"

    def __str__(self):
        return self.ip


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
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = 'agent"."tenant_credentials'
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

    @property
    def username_plain(self) -> str:
        """Valor descifrado del usuario (compatibilidad UI/API)."""
        return _decrypt_value(self.username)

    @property
    def password_plain(self) -> str:
        """Valor descifrado de la contraseña (compatibilidad UI/API)."""
        return _decrypt_value(self.password)

    def ensure_encrypted(self, persist: bool = False) -> bool:
        """
        Cifra username/password si aún están en texto plano. Si ``persist`` es True,
        guarda los cambios en BD.
        """
        changed = False

        new_username = _encrypt_if_needed(self.username)
        new_password = _encrypt_if_needed(self.password)

        if new_username != self.username:
            self.username = new_username
            changed = True

        if new_password != self.password:
            self.password = new_password
            changed = True

        if changed and persist:
            # save() volverá a pasar por _encrypt_if_needed, pero el valor ya está cifrado
            self.save(update_fields=["username", "password", "updated_at"])

        return changed

    def save(self, *args, **kwargs):
        self.username = _encrypt_if_needed(self.username)
        self.password = _encrypt_if_needed(self.password)
        super().save(*args, **kwargs)

    @classmethod
    def get_active_for_tenant(cls, tenant_id: int) -> "TenantCredentials | None":
        try:
            obj = cls.objects.get(tenant_id=tenant_id, is_active=True)
            try:
                obj.ensure_encrypted(persist=True)
            except Exception:
                logger.exception("[CRED] Error asegurando cifrado para tenant_id=%s", tenant_id)
            return obj
        except cls.DoesNotExist:
            return None



class WhitelistCountryPreference(models.Model):
    tenant = models.OneToOneField(
        Tenant,
        on_delete=models.CASCADE,
        related_name="whitelist_country_preference",
    )

    # coincide con Postgres: paises _text
    paises = ArrayField(
        base_field=models.TextField(),
        default=list,
        blank=True,
    )

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        # como tu tabla está en schema agent
        managed = False
        db_table = 'agent"."whitelist_country_preference'
        verbose_name = "Whitelist Country Preference"
        verbose_name_plural = "Whitelist Country Preferences"

    def __str__(self):
        return f"{getattr(self.tenant, 'name', 'Tenant')} ({self.tenant_id})"