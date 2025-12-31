# siem/log360_service.py
import json
import ssl
import urllib.request
import time
import logging
from datetime import date, timedelta, datetime
from typing import Any, List, Optional, Tuple

import os
import requests

logger = logging.getLogger(__name__)

# ============================================================
# Configuración desde variables de entorno
# ============================================================

WEBHOOK_URL = os.environ.get("LOG360_WEBHOOK_URL", "").strip()
WEBHOOK_SECRET = os.environ.get("LOG360_WEBHOOK_SECRET", "") or ""
WEBHOOK_HEADER_NAME = os.environ.get("LOG360_WEBHOOK_HEADER_NAME", "passkey")

BASE_URL = os.environ.get(
    "LOG360_API_BASE_URL",
    "https://log360cloud.manageengine.com/api/v2",
).rstrip("/")

VERIFY_SSL = os.environ.get("LOG360_VERIFY_SSL", "True").lower() == "true"
PAGE_LIMIT = int(os.environ.get("LOG360_PAGE_LIMIT", "50"))
MAX_ALERTS = int(os.environ.get("LOG360_MAX_ALERTS", "10000"))

# Logs seguros (por defecto apagado). Si necesitas diagnosticar en dev:
# export LOG360_DEBUG_LOGS=true
DEBUG_LOGS = (os.environ.get("LOG360_DEBUG_LOGS", "False") or "").strip().lower() in ("1", "true", "yes", "y", "on")

# ============================================================
# Cache en memoria del token (expira antes del próximo HH:00)
# ============================================================

_TOKEN_CACHE = {
    "token": None,          # type: Optional[str]
    "expires_at": 0.0,      # epoch seconds
}

# margen para evitar borde HH:59:59 -> HH:00:00 (latencias)
_TOKEN_SAFETY_SECONDS = int(os.environ.get("LOG360_TOKEN_SAFETY_SECONDS", "45"))


def _seconds_until_next_hour_safe(safety_seconds: int = 45) -> int:
    """
    Retorna segundos hasta el próximo cambio de hora, restando un margen.
    Para cubrir casos donde la rotación sea por hora UTC o por hora local,
    usamos el mínimo TTL entre ambos.
    """
    # UTC
    now_utc = datetime.utcnow()
    next_utc = now_utc.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    ttl_utc = int((next_utc - now_utc).total_seconds()) - int(safety_seconds)

    # Local del servidor
    now_local = datetime.now()
    next_local = now_local.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    ttl_local = int((next_local - now_local).total_seconds()) - int(safety_seconds)

    ttl = min(ttl_utc, ttl_local)
    return max(15, ttl)  # evita ttl <= 0 en el borde de la hora


# ============================================================
# Detección de tokens desde el webhook n8n
# ============================================================

CANDIDATE_KEYS = {
    "acces_token",
    "access_token",
    "token",
    "access-token",
    "access token",
    "access_token".upper(),
    "access_token".title(),
    "access_token".capitalize(),
    "access_token".replace("_", ""),
    "access_token".replace("_", "-"),
}
CANDIDATE_KEYS.update(
    {
        "access_token",
        "access-token",
        "access token",
        "Access_Token",
        "ACCESS_TOKEN",
    }
)


def collect_tokens(obj: Any) -> List[str]:
    """
    Recorre el JSON y devuelve todos los tokens encontrados, en orden.
    """
    found: List[str] = []
    if isinstance(obj, dict):
        lowered = {k.lower() for k in CANDIDATE_KEYS}
        for k, v in obj.items():
            if isinstance(k, str):
                key_norm = k.strip().lower()
                if key_norm in lowered and isinstance(v, str) and v.strip():
                    found.append(v.strip())
            found.extend(collect_tokens(v))
    elif isinstance(obj, list):
        for item in obj:
            found.extend(collect_tokens(item))
    return found


def _fetch_token_from_webhook() -> Tuple[Optional[str], Optional[str]]:
    """
    Llama al webhook n8n y devuelve (token, error).
    Mantiene tu lógica: si hay varios tokens usa el segundo; si hay uno usa ese.
    """
    if not WEBHOOK_URL or "TU-N8N" in WEBHOOK_URL or "XXXXXXXX" in WEBHOOK_URL:
        return None, "LOG360_WEBHOOK_URL no está configurada."

    # (Opcional) si quieres exigir secreto:
    # if not WEBHOOK_SECRET:
    #     return None, "LOG360_WEBHOOK_SECRET no está configurada."

    headers = {WEBHOOK_HEADER_NAME: WEBHOOK_SECRET}
    ctx = ssl.create_default_context() if VERIFY_SSL else ssl._create_unverified_context()
    req = urllib.request.Request(url=WEBHOOK_URL, method="GET", headers=headers)

    try:
        with urllib.request.urlopen(req, timeout=20, context=ctx) as resp:
            status = resp.getcode()
            body = resp.read()
    except Exception as e:
        return None, f"Error al llamar la API del webhook: {e}"

    text = body.decode("utf-8", errors="replace").strip()

    if status // 100 != 2:
        # NO devolvemos text completo en logs; pero sí en el error interno del caller si lo necesita
        return None, f"HTTP {status} al llamar webhook."

    # Intentar JSON
    try:
        data = json.loads(text)
    except Exception:
        # Si no es JSON pero hay texto, se usa como token directo
        if text:
            return text, None
        return None, "La respuesta del webhook no es JSON y está vacía."

    tokens = collect_tokens(data)
    if not tokens:
        return None, "No se encontraron tokens en el JSON del webhook."

    chosen = tokens[1] if len(tokens) >= 2 else tokens[0]
    return chosen, None


def obtener_token_logs360(force_refresh: bool = False) -> Tuple[Optional[str], Optional[str]]:
    """
    Devuelve el token de Logs360 con cache en memoria que expira
    antes del próximo cambio de hora (tu caso real HH:59:59).
    """
    now = time.time()

    if not force_refresh:
        cached = _TOKEN_CACHE.get("token")
        exp = float(_TOKEN_CACHE.get("expires_at") or 0.0)
        if cached and now < exp:
            return cached, None

    token, err = _fetch_token_from_webhook()
    if not token:
        return None, err or "No se pudo obtener token (desconocido)."

    ttl = _seconds_until_next_hour_safe(safety_seconds=_TOKEN_SAFETY_SECONDS)
    _TOKEN_CACHE["token"] = token
    _TOKEN_CACHE["expires_at"] = now + ttl

    if DEBUG_LOGS:
        logger.info("[LOGS360] Token cacheado. ttl=%ss", ttl)

    return token, None


# ============================================================
# Helpers de rango y orden
# ============================================================

def _build_range(from_date: date, to_date: date) -> Tuple[str, str]:
    """
    Construye start_time / end_time ISO8601 con Z para Logs360.
    """
    start_time = f"{from_date.isoformat()}T00:00:00Z"
    end_time = f"{to_date.isoformat()}T23:59:59Z"
    return start_time, end_time


def _parse_time_for_sort(alert: dict) -> str:
    """
    Devuelve el campo Time como string para ordenar.
    """
    t = alert.get("Time") or alert.get("time") or ""
    return str(t)


def _looks_like_auth_error(resp: requests.Response) -> bool:
    """
    Heurística simple para decidir si reintentar por token expirado.
    """
    if resp.status_code in (401, 403):
        return True
    return False


# ============================================================
# Consulta de alertas a Logs360
# ============================================================

def obtener_alertas_logs360(
    query: str = "",
    account_id: str = "",
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
) -> Tuple[list, Optional[str], str, str, str]:
    """
    Devuelve (lista_alertas, error_msg, start_time, end_time, acc_id_usado).

    Modo actual:
    - Ignora from_date / to_date del formulario.
    - Usa siempre un rango fijo de últimos 30 días.
    - Pagina, pero corta al llegar a PAGE_LIMIT.
    """
    # Account ID debe venir desde el tenant
    acc_id = (account_id or "").strip()
    if not acc_id:
        return [], "Account ID de Logs360 no configurado para este tenant.", "", "", ""

    # Rango forzado: últimos 30 días
    today = date.today()
    RANGE_DAYS = 30
    forced_to = today
    forced_from = today - timedelta(days=RANGE_DAYS)
    start_time, end_time = _build_range(forced_from, forced_to)

    # Token desde webhook (cacheado hasta el próximo HH:00)
    token, err_token = obtener_token_logs360()
    if not token:
        return [], f"No se pudo obtener token: {err_token or 'desconocido'}", "", "", ""

    headers = {
        "Authorization": f"Zoho-oauthtoken {token}",
        "account_id": acc_id,
        "Content-Type": "application/json",
    }

    todos: list = []
    current_from = 1
    retried_with_fresh_token = False

    while True:
        body = {
            "query": query or "",
            "start_time": start_time,
            "end_time": end_time,
            "from": current_from,
            "limit": PAGE_LIMIT,
            "response_type": "client",
        }

        if DEBUG_LOGS:
            # NO loggear token, ni body completo en prod. Solo meta mínima.
            logger.info("[LOGS360] POST /alerts from=%s limit=%s acc_id=%s", current_from, PAGE_LIMIT, acc_id)

        try:
            resp = requests.post(
                f"{BASE_URL}/alerts",
                headers=headers,
                json=body,
                timeout=30,
            )
        except requests.RequestException as e:
            return todos, f"Error de red al llamar /alerts: {e}", start_time, end_time, acc_id

        # Retry 1 vez si parece token expirado (tu caso HH:00)
        if _looks_like_auth_error(resp) and not retried_with_fresh_token:
            retried_with_fresh_token = True
            token2, err2 = obtener_token_logs360(force_refresh=True)
            if token2:
                headers["Authorization"] = f"Zoho-oauthtoken {token2}"
                if DEBUG_LOGS:
                    logger.warning("[LOGS360] Reintentando /alerts con token refrescado (auth error %s).", resp.status_code)
                continue
            # si no pudimos refrescar, seguimos con el flujo normal (retornar error)
            if DEBUG_LOGS:
                logger.error("[LOGS360] Falló refresh de token tras auth error: %s", err2)

        if resp.status_code // 100 != 2:
            # NO devolver resp.text completo (puede traer datos sensibles o enormes)
            return (
                todos,
                f"HTTP {resp.status_code} al llamar /alerts.",
                start_time,
                end_time,
                acc_id,
            )

        try:
            data = resp.json()
        except ValueError:
            return (
                todos,
                "La respuesta de /alerts no es JSON.",
                start_time,
                end_time,
                acc_id,
            )

        if "error" in data:
            err = data.get("error") or {}
            code = err.get("code")
            title = err.get("title")
            detail = err.get("detail")

            # Mensaje acotado (sin volcados grandes)
            msg = f"Error Logs360 (code {code}): {title or 'Forbidden'}"
            if detail:
                # recorta por si viene muy largo
                detail_s = str(detail)
                if len(detail_s) > 300:
                    detail_s = detail_s[:300] + "..."
                msg += f" — {detail_s}"

            return todos, msg, start_time, end_time, acc_id

        batch = data.get("data") or []
        if not isinstance(batch, list):
            return (
                todos,
                "Estructura inesperada de /alerts.",
                start_time,
                end_time,
                acc_id,
            )

        # Acumulamos resultados
        todos.extend(batch)

        # Cortar por PAGE_LIMIT o MAX_ALERTS
        if len(todos) >= PAGE_LIMIT or len(todos) >= MAX_ALERTS:
            todos = todos[: min(PAGE_LIMIT, MAX_ALERTS)]
            break

        # Si vino menos que el límite, no hay más páginas
        if len(batch) < PAGE_LIMIT:
            break

        # Siguiente página
        current_from += PAGE_LIMIT

    # Ordenar por Time desc
    todos.sort(key=_parse_time_for_sort, reverse=True)

    # Asegurar máximo PAGE_LIMIT
    if len(todos) > PAGE_LIMIT:
        todos = todos[:PAGE_LIMIT]

    return todos, None, start_time, end_time, acc_id
