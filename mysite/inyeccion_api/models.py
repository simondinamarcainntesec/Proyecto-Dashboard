from django.db import models

# Create your models here.
from django.db import models

class Alarm(models.Model):
    # --- CAMBIO AQUÍ ---
    # Usamos alertid como el identificador único.
    alertid = models.CharField(max_length=255, unique=True, help_text="ID único de la alarma (alertid) proveniente de la API")

    # --- El resto de los campos no cambia ---
    event_time = models.DateTimeField(null=True, blank=True, help_text="Fecha y hora del evento (convertido a America/Santiago)")
    tags = models.TextField(blank=True, help_text="Tags de AOTAGS, formateados y separados por comas")
    severity = models.CharField(max_length=100, blank=True)
    device_name = models.CharField(max_length=255, blank=True, help_text="Extraído del mensaje (msg_device_name)")
    action = models.TextField(blank=True)
    actions = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Alarma {self.alertid} - {self.device_name} ({self.severity})"

    class Meta:
        ordering = ['-event_time']