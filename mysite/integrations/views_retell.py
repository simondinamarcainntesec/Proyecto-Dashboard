import logging
import requests

from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required

from tenants.decorators import tenant_required  # en tu portal ya lo usas

logger = logging.getLogger(__name__)

RETELL_CREATE_WEB_CALL_URL = "https://api.retellai.com/v2/create-web-call"

@login_required
@tenant_required
@require_POST
def retell_create_web_call(request):
    tenant = getattr(request, "tenant", None)

    # 1) Resolver agent_id (multi-tenant friendly)
    # Si más adelante guardas un agent_id por tenant (recomendado), cámbialo aquí.
    agent_id = getattr(tenant, "retell_agent_id", None) or getattr(settings, "RETELL_AGENT_ID", "")
    api_key = getattr(settings, "RETELL_API_KEY", "") or ""
    timeout = getattr(settings, "RETELL_TIMEOUT", 20)

    if not api_key or not agent_id:
        return JsonResponse(
            {"ok": False, "error": "RETELL_API_KEY / RETELL_AGENT_ID no configurados"},
            status=500,
        )

    headers = {
        "Authorization": f"Bearer {api_key}",  # Retell exige Bearer API key :contentReference[oaicite:1]{index=1}
        "Content-Type": "application/json",
    }
    payload = {"agent_id": agent_id}  # agent_id requerido :contentReference[oaicite:2]{index=2}

    try:
        resp = requests.post(
            RETELL_CREATE_WEB_CALL_URL,
            json=payload,
            headers=headers,
            timeout=timeout,
        )
        if not resp.ok:
            logger.error("[RETELL] create-web-call failed status=%s body=%s", resp.status_code, resp.text)
            return JsonResponse(
                {"ok": False, "error": "Retell error", "status": resp.status_code, "body": resp.text},
                status=502,
            )

        data = resp.json()
        return JsonResponse({
            "ok": True,
            "access_token": data.get("access_token"),
            "call_id": data.get("call_id"),
        })
    except Exception:
        logger.exception("[RETELL] Error inesperado creando web call")
        return JsonResponse({"ok": False, "error": "Error inesperado creando web call"}, status=500)
