# tenants/models.py
from django.db import models

class Tenant(models.Model):
    name = models.CharField(max_length=255)
    # ...

class TenantDashboardEmbed(models.Model):
    tenant = models.OneToOneField(
        Tenant,
        on_delete=models.CASCADE,
        related_name="dashboard_iframe",
    )
    iframe_url = models.URLField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.tenant.name} embed"
