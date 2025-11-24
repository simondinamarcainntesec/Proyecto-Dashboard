# tenants/utils.py
from django.conf import settings
from tenants.models import Tenant
from tenants.models import Client  # <-- o desde el app donde está tu modelo Client
import logging

logger = logging.getLogger(__name__)

def user_can_view_monitoring(user) -> bool:
    """
    Une tenant_client con tenant_tenant usando tenant_id y revisa si,
    para ese tenant, hay algún ID configurado en:
      - alarms_one_id
      - logs360siem_id
      - site24x7_id

    Si no hay tenant, no hay client o algo falla, devuelve False.
    """
    if not getattr(user, "is_authenticated", False):
        return False

    try:
        client = (
            Client.objects
            .select_related("tenant")
            .filter(user=user)
            .first()
        )
        if not client or not client.tenant:
            return False

        tenant = client.tenant

        alarms_one_ok = bool((getattr(tenant, "alarms_one_id", "") or "").strip())
        logs360_ok    = bool((getattr(tenant, "logs360siem_id", "") or "").strip())
        site24x7_ok   = bool((getattr(tenant, "site24x7_id", "") or "").strip())

        return alarms_one_ok or logs360_ok or site24x7_ok

    except Exception as e:
        logger.exception("[user_can_view_monitoring] Error evaluando permisos: %s", e)
        return False