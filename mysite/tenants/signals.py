# tenants/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Tenant, TenantDashboardEmbed


@receiver(post_save, sender=Tenant)
def ensure_tenant_dashboard_iframe(sender, instance: Tenant, created: bool, **kwargs):
    """
    'Trigger' lógico que se ejecuta cuando se crea o se guarda un Tenant.

    - Si el Tenant tiene site24x7_id (no nulo ni vacío),
      se asegura que exista un TenantDashboardEmbed ligado a él.
    - Si ya existe, NO tocamos el iframe_url (lo gestionas tú manualmente).
    """

    site24x7_id = (instance.site24x7_id or "").strip()

    # Solo actuamos si tiene site24x7_id
    if not site24x7_id:
        return

    # Si ya existe el embed, no hacemos nada (no queremos pisar el iframe_url)
    embed, created_embed = TenantDashboardEmbed.objects.get_or_create(
        tenant=instance,
        defaults={
            "iframe_url": "",  # lo dejas vacío para rellenar manualmente
        },
    )

    if created_embed:
        # Log opcional
        print(
            f"[TenantDashboardEmbed] Creado para tenant='{instance.name}' "
            f"(site24x7_id={site24x7_id})"
        )
