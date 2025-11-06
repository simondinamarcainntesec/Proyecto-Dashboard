# tenants/managers.py
from django.db import models
from tenants.context import current_tenant

class TenantManager(models.Manager):
    """
    Manager que aplica filtro automático por tenant actual.
    Si no hay tenant en contexto, devuelve queryset vacío para evitar fugas.
    """
    def get_queryset(self):
        qs = super().get_queryset()
        t = current_tenant.get()
        return qs.none() if t is None else qs.filter(tenant=t)

# Úsalo en tus modelos multi-tenant:
#
# class Alarm(TenantScopedModel):
#     ...
#     objects = TenantManager()
#     all_objects = models.Manager()  # sin filtro (solo uso administrativo)
