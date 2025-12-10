from django.db import models

class Alarm(models.Model):
    alertid = models.CharField(max_length=255, unique=True, help_text="ID único de la alarma (alertid) proveniente de la API")
    event_time = models.DateTimeField(null=True, blank=True, help_text="Fecha y hora del evento (convertido a America/Santiago)")
    tags = models.TextField(blank=True, help_text="Tags de AOTAGS, formateados y separados por comas")
    severity = models.CharField(max_length=100, blank=True)
    msg_severity = models.CharField(max_length=100, blank=True, help_text="Severidad derivada desde message/log_details")
    device_name = models.CharField(max_length=255, blank=True, help_text="Extraído del mensaje (msg_device_name)")
    action = models.TextField(blank=True)
    actions = models.TextField(blank=True)
    level = models.CharField(max_length=100, blank=True, help_text="Level extraído de message/log_details")
    log_description = models.TextField(blank=True, help_text="Log Description extraído de message/log_details")
    subtype = models.CharField(max_length=100, blank=True, help_text="Subtype extraído de message/log_details")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        base = f"Alarma {self.alertid} - {self.device_name} ({self.severity})"
        return f"{base} [msg_sev={self.msg_severity}]" if self.msg_severity else base

    class Meta:
        ordering = ['-event_time']
