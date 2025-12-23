# integrations/views_retell.py
import logging
import requests

from django.conf import settings
from django.http import JsonResponse, HttpResponseForbidden
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


def _meta_matches_request(request, call_data: dict) -> bool:
    """
    Valida que el call_id consultado pertenezca al mismo tenant/usuario que lo creó.
    Si no hay metadata (por compatibilidad), permite el acceso pero deja log.
    """
    meta = call_data.get("metadata") or {}
    meta_tenant = (meta.get("tenant") or "").strip()
    meta_user = (meta.get("username") or "").strip()

    req_tenant = (_get_empresa_from_tenant(request) or "").strip()
    req_user = (getattr(request.user, "username", "") or "").strip()

    if not meta_tenant and not meta_user:
        logger.warning(
            "[RETELL] get-call sin metadata (se permite por compatibilidad) call_id=%s req_user=%s req_tenant=%s",
            call_data.get("call_id"),
            req_user,
            req_tenant,
        )
        return True

    # Comparación tenant case-insensitive (por seguridad ante diferencias de casing)
    if meta_tenant and meta_tenant.lower() != req_tenant.lower():
        return False
    if meta_user and meta_user != req_user:
        return False
    return True


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

    # si no hay teléfono, no se crea llamada
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
        return JsonResponse(
            {
                "ok": True,
                "access_token": data.get("access_token"),
                "call_id": data.get("call_id"),
            }
        )

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

        # Seguridad básica: que el call pertenezca al mismo tenant/usuario que lo creó
        if not _meta_matches_request(request, data):
            logger.warning(
                "[RETELL] get-call FORBIDDEN call_id=%s req_user=%s req_tenant=%s meta=%s",
                call_id,
                getattr(request.user, "username", ""),
                _get_empresa_from_tenant(request),
                (data.get("metadata") or {}),
            )
            return HttpResponseForbidden("Forbidden")

        call_status = (data.get("call_status") or "").strip().lower()
        end_ts = data.get("end_timestamp")

        # Regla: solo entregar transcripción/URLs cuando la llamada ya terminó
        is_final = (call_status == "ended") or bool(end_ts)

        call_payload = {
            "call_id": data.get("call_id"),
            "call_status": data.get("call_status"),
            "disconnection_reason": data.get("disconnection_reason"),
            "start_timestamp": data.get("start_timestamp"),
            "end_timestamp": data.get("end_timestamp"),
            "transcript_available": bool(is_final),
            # Solo final (cuando cuelga)
            "transcript": data.get("transcript") if is_final else None,
            "public_log_url": data.get("public_log_url") if is_final else None,
            "recording_url": data.get("recording_url") if is_final else None,
        }

        return JsonResponse({"ok": True, "call": call_payload})

    except Exception:
        logger.exception("[RETELL] get-call error")
        return JsonResponse({"ok": False, "error": "Error inesperado"}, status=500)
