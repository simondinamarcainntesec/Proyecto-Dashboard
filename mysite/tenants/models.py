# tenants/models.py
from django.db import models
from django.contrib.auth.models import User


class Tenant(models.Model):
    """
    Representa una empresa o cliente global (tenant).
    Agrupa a los usuarios y clientes que pertenecen a una misma organización.
    """
    name = models.CharField(
        max_length=255,
        unique=True,
        help_text="Nombre de la empresa (campo 'Empresa' de la API)"
    )
    alarms_one_id = models.IntegerField(
        null=True, blank=True,
        help_text="ID de AlarmsOne"
    )
    logs360siem_id = models.IntegerField(
        null=True, blank=True,
        help_text="ID de Logs360SIEM"
    )
    site24x7_id = models.IntegerField(
        null=True, blank=True,
        help_text="ID de Site24x7"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Tenant"
        verbose_name_plural = "Tenants"


class Client(models.Model):
    """
    Representa un cliente final asociado a un Tenant.
    Cada cliente puede vincularse opcionalmente con un usuario de Django.
    """
    api_id = models.IntegerField(
        unique=True,
        help_text="ID numérico del cliente (campo 'N' de la API)"
    )
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name='clients',
        help_text="Empresa a la que pertenece el cliente"
    )
    name = models.CharField(
        max_length=255,
        help_text="Nombre del cliente (campo 'Nombre' de la API)"
    )
    email = models.EmailField(
        unique=True,
        help_text="Email del cliente (campo 'Email' de la API)"
    )
    phone = models.CharField(
        max_length=50,
        null=True, blank=True,
        help_text="Teléfono del cliente (campo 'Telefono' de la API)"
    )
    telegram_id = models.CharField(
        max_length=100,
        null=True, blank=True,
        help_text="ID de Telegram del cliente (campo 'Telegram' de la API)"
    )
    user = models.OneToOneField(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='tenant_client_profile',
        help_text="Usuario Django vinculado a este cliente"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        """
        Asegura que el email se guarde siempre en minúsculas para evitar duplicados insensibles a mayúsculas.
        """
        if self.email:
            self.email = self.email.lower()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.tenant.name})"

    class Meta:
        verbose_name = "Cliente"
        verbose_name_plural = "Clientes"
