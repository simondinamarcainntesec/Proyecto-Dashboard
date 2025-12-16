# integrations/views_retell.py
import logging
import requests

from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_GET
from django.contrib.auth.decorators import login_required

from tenants.decorators import tenant_required

logger = logging.getLogger(__name__)

RETELL_CREATE_WEB_CALL_URL = "https://api.retellai.com/v2/create-web-call"


def _get_user_full_name(user) -> str:
    try:
        full = (user.get_full_name() or "").strip()
        if full:
            return full
    except Exception:
        pass
    return (getattr(user, "username", "") or "").strip() or "Usuario"


def _get_user_phone(user):
    for attr in ("phone", "phone_number", "telefono", "tel"):
        v = (getattr(user, attr, "") or "").strip()
        if v:
            return v
    return None


def _get_empresa_from_tenant(request) -> str:
    tenant = getattr(request, "tenant", None)
    name = (getattr(tenant, "name", "") or "").strip()
    return name or "Inntesec"


@require_POST
@login_required
@tenant_required
def retell_create_web_call(request):
    api_key = (getattr(settings, "RETELL_API_KEY", "") or "").strip()
    agent_id = (getattr(settings, "RETELL_AGENT_ID", "") or "").strip()
    timeout = int(getattr(settings, "RETELL_TIMEOUT", 25))

    if not api_key or not agent_id:
        return JsonResponse(
            {"ok": False, "error": "RETELL_API_KEY / RETELL_AGENT_ID no configurados en settings"},
            status=500,
        )

    empresa = _get_empresa_from_tenant(request)
    nombre_usuario = _get_user_full_name(request.user)
    number_web = _get_user_phone(request.user)

    # ✅ si no hay teléfono, no se crea llamada
    if not number_web:
        return JsonResponse(
            {"ok": False, "error": "NO_PHONE", "detail": "El usuario no tiene teléfono registrado."},
            status=400,
        )

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "agent_id": agent_id,
        "retell_llm_dynamic_variables": {
            "number_web": number_web,
            "nombre_usuario": nombre_usuario,
            "empresa": empresa,
        },
        "metadata": {
            "source": "inntesec_dashboard",
            "tenant": empresa,
            "username": getattr(request.user, "username", ""),
        },
    }

    try:
        resp = requests.post(
            RETELL_CREATE_WEB_CALL_URL,
            json=payload,
            headers=headers,
            timeout=timeout,
        )

        logger.info(
            "[RETELL] create-web-call status=%s user=%s tenant=%s body=%s",
            resp.status_code,
            getattr(request.user, "username", ""),
            empresa,
            resp.text[:1500],
        )

        if not resp.ok:
            return JsonResponse(
                {"ok": False, "error": "Retell error", "status": resp.status_code, "body": resp.text[:2000]},
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
        return JsonResponse({"ok": False, "error": "Error inesperado"}, status=500)


@require_GET
@login_required
@tenant_required
def retell_get_call(request, call_id: str):
    api_key = (getattr(settings, "RETELL_API_KEY", "") or "").strip()
    timeout = int(getattr(settings, "RETELL_TIMEOUT", 25))

    if not api_key:
        return JsonResponse({"ok": False, "error": "RETELL_API_KEY no configurado"}, status=500)

    url = f"https://api.retellai.com/v2/get-call/{call_id}"
    headers = {"Authorization": f"Bearer {api_key}"}

    try:
        resp = requests.get(url, headers=headers, timeout=timeout)
        logger.info("[RETELL] get-call call_id=%s status=%s body=%s", call_id, resp.status_code, resp.text[:1500])

        if not resp.ok:
            return JsonResponse(
                {"ok": False, "error": "Retell error", "status": resp.status_code, "body": resp.text[:2000]},
                status=502,
            )

        data = resp.json()
        return JsonResponse({
            "ok": True,
            "call": {
                "call_id": data.get("call_id"),
                "call_status": data.get("call_status"),
                "disconnection_reason": data.get("disconnection_reason"),
                "transcript": data.get("transcript"),
                "public_log_url": data.get("public_log_url"),
                "recording_url": data.get("recording_url"),
            }
        })

    except Exception:
        logger.exception("[RETELL] get-call error")
        return JsonResponse({"ok": False, "error": "Error inesperado"}, status=500)
