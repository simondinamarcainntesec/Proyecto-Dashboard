# siem/log360_service.py
import json
import ssl
import urllib.request
from datetime import date, timedelta
from typing import Any, List, Optional, Tuple

import os
import requests

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

# ============================================================
# Detección de tokens desde el webhook n8n
# ============================================================

# Claves posibles donde puede venir el token
CANDIDATE_KEYS = {
    "acces_token",
    "access_token",
    "token",
    "access_token",
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
        "access_token".upper(),
        "access_token".title(),
        "acces_token",
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


def obtener_token_logs360() -> Tuple[Optional[str], Optional[str]]:
    """
    Llama al webhook n8n y devuelve el token de Logs360.
    Si hay varios tokens, usa el segundo; si hay uno, usa ese.
    """
    if not WEBHOOK_URL or "TU-N8N" in WEBHOOK_URL or "XXXXXXXX" in WEBHOOK_URL:
        return None, "LOG360_WEBHOOK_URL no está configurada."

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
        return None, f"HTTP {status} al llamar webhook. Cuerpo: {text}"

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
        if text:
            return None, "No se encontraron tokens en el JSON del webhook."
        return None, "Respuesta vacía del webhook."

    # Segundo token si hay 2 o más (Logs360), si no el único
    if len(tokens) >= 2:
        chosen = tokens[1]
    else:
        chosen = tokens[0]

    return chosen, None


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
    # Token desde webhook
    token, err_token = obtener_token_logs360()
    if not token:
        return [], f"No se pudo obtener token: {err_token or 'desconocido'}", "", "", ""

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

    print("========== SIEM / Django ==========")
    print(f"[SIEM] Account ID        : {acc_id}")
    print(f"[SIEM] Token (inicio)    : {token[:30]}...")
    print(f"[SIEM] Query             : {query!r}")
    print(f"[SIEM] Rango (FORZADO)   : {forced_from} -> {forced_to}")
    print(f"[SIEM] Rango UTC (Z)     : {start_time} -> {end_time}")
    print("===================================")

    headers = {
        "Authorization": f"Zoho-oauthtoken {token}",
        "account_id": acc_id,
        "Content-Type": "application/json",
    }

    todos: list = []
    current_from = 1

    while True:
        body = {
            "query": query or "",
            "start_time": start_time,
            "end_time": end_time,
            "from": current_from,
            "limit": PAGE_LIMIT,
            "response_type": "client",
        }

        print(f"[SIEM] POST /alerts from={current_from} body= {json.dumps(body)}")

        try:
            resp = requests.post(
                f"{BASE_URL}/alerts",
                headers=headers,
                json=body,
                timeout=30,
            )
        except requests.RequestException as e:
            return todos, f"Error de red al llamar /alerts: {e}", start_time, end_time, acc_id

        print(f"[SIEM] /alerts HTTP status: {resp.status_code}")

        if resp.status_code // 100 != 2:
            return (
                todos,
                f"HTTP {resp.status_code} al llamar /alerts: {resp.text}",
                start_time,
                end_time,
                acc_id,
            )

        try:
            data = resp.json()
        except ValueError:
            return (
                todos,
                f"La respuesta de /alerts no es JSON: {resp.text[:1000]}",
                start_time,
                end_time,
                acc_id,
            )

        if "error" in data:
            err = data.get("error") or {}
            code = err.get("code")
            title = err.get("title")
            detail = err.get("detail")

            msg = f"Error Logs360 (code {code}): {title or 'Forbidden'}"
            if detail:
                msg += f" — {detail}"

            return todos, msg, start_time, end_time, acc_id

        batch = data.get("data") or []
        if not isinstance(batch, list):
            return (
                todos,
                f"Estructura inesperada de /alerts: {json.dumps(data, ensure_ascii=False)[:1000]}",
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
