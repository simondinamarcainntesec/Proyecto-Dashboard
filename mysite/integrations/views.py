# integrations/views.py
from django.shortcuts import render
from django.http import JsonResponse
from django.utils.timezone import now
from datetime import timedelta
import logging, os
from inyeccion_api.models import Alarm
from inyeccion_api.utils import _map_api_alarm_to_model
import pathlib
from integrations.alarmsone import list_alarms_all
from django.contrib.auth.decorators import login_required
from tenants.decorators import tenant_required
from django.views.decorators.http import require_POST
import requests, json
import logging


logger = logging.getLogger(__name__)

BASE_DIR = pathlib.Path(__file__).resolve().parent.parent.parent 
TOKEN_FILE = BASE_DIR / "token.txt"

def obtener_alarmas_desde_api(request):
    """
    Obtiene las alarmas desde la API y las guarda en la base de datos.
    Se ejecuta solo al ingresar a la página o presionar "Refresh".
    """
    try:
        logging.info("Ejecutando ingesta manual de API")

        # Leer token
        if not os.path.exists(TOKEN_FILE):
            return JsonResponse({"error": "No se encontró token.txt"}, status=400)

        with open(TOKEN_FILE, "r") as f:
            API_TOKEN = f.read().strip()

        from_dt = now() - timedelta(days=7)
        to_dt = now()

        result = list_alarms_all(
        from_dt=int(from_dt.timestamp() * 1000),
        to_dt=int(to_dt.timestamp() * 1000),
        token=API_TOKEN
)
        alarms_data = result.get("alarms", []) if result else []

        count_inserted = 0
        for item in alarms_data:
            alarm_obj = _map_api_alarm_to_model(item)
            if not alarm_obj:
                continue
            if Alarm.objects.filter(alertid=alarm_obj.alertid).exists():
                continue
            alarm_obj.save()
            count_inserted += 1

        return JsonResponse({
            "status": "ok",
            "nuevas_alarmas": count_inserted,
            "total_recibidas": len(alarms_data)
        })

    except Exception as e:
        logging.exception(f"Error durante la ingesta manual: {e}")
        return JsonResponse({"error": str(e)}, status=500)

@login_required
@tenant_required
def retell_call_window(request):
    # Si necesitas el tenant en contexto:
    tenant = getattr(request, "tenant", None)
    return render(request, "integrations/retell_call_window.html", {
        "tenant": tenant,
    })


CHAT_WEBHOOK_URL = os.environ.get("CHAT_WEBHOOK_URL", "").strip() or "https://iaproductivo.inntesec.cl/webhook/Chat_InntesecAgent_Dashboard"
CHAT_WEBHOOK_PASSKEY = (os.environ.get("CHAT_WEBHOOK_PASSKEY") or "").strip()
CHAT_WEBHOOK_TIMEOUT = int(os.environ.get("CHAT_WEBHOOK_TIMEOUT", "20"))
_raw_verify = (os.environ.get("CHAT_WEBHOOK_VERIFY_SSL", "True") or "").strip().lower()
CHAT_WEBHOOK_VERIFY_SSL = _raw_verify in ("1", "true", "yes", "y", "on")


def _parse_webhook_replies(resp: "requests.Response") -> list[str]:
    """
    Devuelve una lista de mensajes (strings) en orden.
    Soporta:
      - JSON dict con keys: replies/messages/outputs/results/items/data
      - JSON list en la raíz
      - Texto plano (1 mensaje; opcionalmente separable por \n---\n)
    """
    ctype = (resp.headers.get("Content-Type") or "").lower()

    def coerce(value) -> list[str]:
        out: list[str] = []
        if value is None:
            return out

        # Root list
        if isinstance(value, list):
            for item in value:
                if isinstance(item, str) and item.strip():
                    out.append(item.strip())
                elif isinstance(item, dict):
                    for k in ("text", "message", "reply", "content", "output"):
                        v = item.get(k)
                        if isinstance(v, str) and v.strip():
                            out.append(v.strip())
                            break
            return out

        # Root dict
        if isinstance(value, dict):
            # Multi-message containers
            for k in ("replies", "messages", "outputs", "results", "items", "data"):
                v = value.get(k)
                if isinstance(v, list):
                    out = coerce(v)
                    if out:
                        return out

            # Single-message keys
            for k in ("reply", "message", "response", "text", "answer", "output"):
                v = value.get(k)
                if isinstance(v, str) and v.strip():
                    return [v.strip()]

            # Fallback: stringify dict
            return [json.dumps(value, ensure_ascii=False)]

        # Root string
        if isinstance(value, str) and value.strip():
            return [value.strip()]

        return out

    # JSON
    if "application/json" in ctype:
        data = resp.json()
        replies = coerce(data)
        return replies or ["OK"]

    # Plain text
    text = (resp.text or "").strip()
    if not text:
        return ["OK"]

    # (Opcional) Si el webhook envía varios mensajes en texto con separador claro:
    if "\n---\n" in text:
        parts = [p.strip() for p in text.split("\n---\n") if p.strip()]
        return parts or [text]

    return [text]


@login_required
@tenant_required
@require_POST
def chat_send_message(request):
    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "JSON inválido"}, status=400)

    msg = (payload.get("message") or "").strip()
    if not msg:
        return JsonResponse({"ok": False, "error": "Mensaje vacío"}, status=400)

    if not CHAT_WEBHOOK_PASSKEY:
        return JsonResponse({"ok": False, "error": "CHAT_WEBHOOK_PASSKEY no configurada"}, status=500)

    tenant = getattr(request, "tenant", None)

    # Nombre amigable (evita mandar correo si username=correo)
    u = request.user
    full_name = (u.get_full_name() or "").strip()
    display_name = full_name or (getattr(u, "first_name", "") or "").strip() or (getattr(u, "username", "") or "Usuario")

    # IMPORTANTE: header debe ser "Passkey" (sin dos puntos). Para descartar case-sensitivity,
    # mandamos ambas variantes.
    headers = {
        "Passkey": CHAT_WEBHOOK_PASSKEY,
        "passkey": CHAT_WEBHOOK_PASSKEY,
    }

    # Parámetros: asumo que el webhook recibe "message".
    params = {
        "message": msg,
        "tenant_id": getattr(tenant, "id", ""),
        "tenant_name": getattr(tenant, "name", ""),
        "user": display_name,
        "user_id": u.id,
    }

    try:
        r = requests.get(
            CHAT_WEBHOOK_URL,
            headers=headers,
            params=params,
            timeout=CHAT_WEBHOOK_TIMEOUT,
            verify=CHAT_WEBHOOK_VERIFY_SSL,
        )

        # Logging útil sin filtrar secreto
        logger.info(
            "Chat webhook status=%s url=%s header_passkey_len=%s",
            r.status_code,
            r.url,
            len(CHAT_WEBHOOK_PASSKEY),
        )

        if r.status_code == 403:
            # No crashear: devolver mensaje claro al frontend
            return JsonResponse(
                {"ok": False, "error": "Webhook rechazó la solicitud (403). Revisa Passkey/permiso de origen."},
                status=502,
            )

        r.raise_for_status()

    except requests.RequestException:
        logger.exception("Chat webhook request failed")
        return JsonResponse({"ok": False, "error": "No fue posible contactar el webhook de chat"}, status=502)

    try:
        replies = _parse_webhook_replies(r)
    except Exception:
        logger.exception("Chat webhook parse failed")
        return JsonResponse({"ok": False, "error": "Respuesta inválida desde webhook"}, status=502)

    return JsonResponse({
        "ok": True,
        "replies": replies,                  # NUEVO: lista de mensajes
        "reply": replies[-1] if replies else ""  # compat: último mensaje
    })


@login_required
@tenant_required
def chat_window(request):
    tenant = getattr(request, "tenant", None)

    u = request.user
    full_name = (u.get_full_name() or "").strip()
    display_name = full_name or (getattr(u, "first_name", "") or "").strip() or (getattr(u, "username", "") or "Usuario")

    return render(request, "integrations/chat_window.html", {
        "tenant": tenant,
        "display_name": display_name,
    })
