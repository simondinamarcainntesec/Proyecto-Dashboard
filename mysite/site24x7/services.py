# site24x7/services.py
import json
import os
import ssl
import urllib.request
from pathlib import Path
from typing import Any, List, Dict

import requests

# ============================================================
# Config desde variables de entorno
# (mismo webhook que Logs360, pero separado por claridad)
#
# Esperados en .env:
#   SITE24X7_WEBHOOK_URL
#   SITE24X7_WEBHOOK_SECRET
#   SITE24X7_WEBHOOK_HEADER_NAME  (opcional, default "passkey")
#   SITE24X7_API_BASE_URL         (opcional)
#   SITE24X7_VERIFY_SSL           (opcional, "True"/"False")
# ============================================================

WEBHOOK_URL = os.environ.get("SITE24X7_WEBHOOK_URL", "").strip()
WEBHOOK_SECRET = os.environ.get("SITE24X7_WEBHOOK_SECRET", "") or ""
WEBHOOK_HEADER_NAME = os.environ.get("SITE24X7_WEBHOOK_HEADER_NAME", "passkey")

SITE24X7_BASE_URL = os.environ.get(
    "SITE24X7_API_BASE_URL",
    "https://www.site24x7.com/api",
).rstrip("/")

VERIFY_SSL = os.environ.get("SITE24X7_VERIFY_SSL", "True").lower() == "true"

TOKEN_FILE = Path(__file__).resolve().parent / "token.txt"

AnyType = Any  # alias simple para tipado

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

CURRENT_STATUS_PATH = "/msp/customers/monitors/status"  # Customer Wise Monitor Status


# -----------------------------------
# Utilidades para extraer el token
# -----------------------------------
def collect_tokens(obj: Any) -> List[str]:
    """
    Recorre el JSON y junta todos los posibles tokens.
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


def get_site24x7_token() -> str:
    """
    Llama al webhook y devuelve el token de Site24x7.
    Siempre toma el 3er token; si no hay 3, usa el último.
    """
    if not WEBHOOK_URL:
        raise RuntimeError("SITE24X7_WEBHOOK_URL no está configurada.")

    headers = {WEBHOOK_HEADER_NAME: WEBHOOK_SECRET}
    ctx = ssl.create_default_context() if VERIFY_SSL else ssl._create_unverified_context()
    req = urllib.request.Request(url=WEBHOOK_URL, method="GET", headers=headers)

    try:
        with urllib.request.urlopen(req, timeout=20, context=ctx) as resp:
            status = resp.getcode()
            body = resp.read()
    except Exception as e:
        raise RuntimeError(f"Error al llamar al webhook de token: {e}")

    text = body.decode("utf-8", errors="replace").strip()

    if status // 100 != 2:
        raise RuntimeError(f"Webhook de token respondió HTTP {status}: {text}")

    # Intentar JSON como en el script original
    try:
        data = json.loads(text)
        tokens = collect_tokens(data)

        if not tokens:
            raise RuntimeError("No se encontraron tokens en el JSON del webhook.")

        # 3er token para Site24x7 (si existe), si no, el último
        if len(tokens) >= 3:
            chosen = tokens[2]
        else:
            chosen = tokens[-1]

        try:
            TOKEN_FILE.write_text(chosen, encoding="utf-8")
        except Exception:
            # Si falla el guardado no rompemos el flujo
            pass

        return chosen

    except json.JSONDecodeError:
        # Si no es JSON, usamos el cuerpo como token simple
        if not text:
            raise RuntimeError("Respuesta vacía del webhook de token (no es JSON).")
        try:
            TOKEN_FILE.write_text(text, encoding="utf-8")
        except Exception:
            pass
        return text


# -----------------------------------
# Llamado a Site24x7 – Customer Wise Monitor Status
# -----------------------------------
def fetch_customer_status(access_token: str, zaaid: str) -> Dict[str, AnyType]:
    """
    Llama a /msp/customers/monitors/status y devuelve el cliente del zaaid.
    """
    headers = {
        "Accept": "application/json; version=2.0",
        "Authorization": f"Zoho-oauthtoken {access_token}",
    }

    url = f"{SITE24X7_BASE_URL}{CURRENT_STATUS_PATH}"
    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    customers = data.get("data", [])
    for customer in customers:
        if str(customer.get("zaaid")) == str(zaaid):
            return customer

    return {}  # no encontrado


def build_counters(monitors: List[Dict[str, AnyType]]) -> Dict[str, int]:
    """
    A partir de los monitores arma contadores por status.
    """
    counters = {
        "down": 0,       # 0
        "up": 0,         # 1
        "trouble": 0,    # 2
        "critical": 0,   # 3
        "suspended": 0,  # 5
    }

    for m in monitors:
        st = m.get("status")
        if st == 0:
            counters["down"] += 1
        elif st == 1:
            counters["up"] += 1
        elif st == 2:
            counters["trouble"] += 1
        elif st == 3:
            counters["critical"] += 1
        elif st == 5:
            counters["suspended"] += 1

    return counters
