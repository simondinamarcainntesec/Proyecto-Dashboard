from django.db import models
from django.contrib.auth.models import AbstractUser
from django.conf import settings
from django.db.models.functions import Lower



class Tenant(models.Model):
    name = models.CharField(max_length=255, unique=True, help_text="Nombre de la empresa (campo 'Empresa' de la API)")
    alarms_one_id = models.TextField(null=True, blank=True, help_text="ID de AlarmsOne")
    logs360siem_id = models.TextField(null=True, blank=True, help_text="ID de Logs360SIEM")
    site24x7_id = models.TextField(null=True, blank=True, help_text="ID de Site24x7")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class Client(models.Model):
    api_id = models.IntegerField(unique=True, help_text="ID numérico del cliente (campo 'N' de la API)")
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


class TenantUser(AbstractUser):
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='users'
    )
    Alarma_Telefono = models.BooleanField(default=False)
    Alarma_Correo = models.BooleanField(default=False)
    Alarma_Telegram = models.BooleanField(default=False)
    

    def __str__(self):
        return f"{self.username} ({self.tenant.name if self.tenant else 'Sin tenant'})"