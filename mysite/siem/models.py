# tenants/models.py
from django.db import models

class Tenant(models.Model):
    # tu modelo real (ya existe)
    pass


class TenantDashboardEmbed(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="dashboard_embeds")

    # AJUSTA estos nombres según tu tabla real
    dashboard_key = models.CharField(max_length=64)     # ej: "siem", "innmonitor", "site24x7", etc.
    iframe_url = models.URLField(max_length=2000)       # el src del iframe
    is_active = models.BooleanField(default=True)       # opcional pero recomendado

    class Meta:
        db_table = "tenants_tenantdashboardembed"
        managed = False

    def __str__(self):
        return f"{self.tenant_id} - {self.dashboard_key}"