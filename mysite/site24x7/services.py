import json
import ssl
import urllib.request
from pathlib import Path
from typing import Any, List, Dict

import requests

# =========================
# Configuración TOKEN WEBHOOK
# =========================
TOKEN_URL = "https://iaproductivo.inntesec.cl/webhook/3c850e31-e699-4fa6-9fed-513d4ccd281b"
SECRET = "@L^E4$h!f^r1VmwD#c1B#C8XzM#B4pON"
HEADER_NAME = "passkey"
VERIFY_SSL = True

TOKEN_FILE = Path(__file__).resolve().parent / "token.txt"

CANDIDATE_KEYS = {
    "acces_token", "access_token", "token",
    "access-token", "access token",
    "ACCESS_TOKEN", "Access_Token",
}

# =========================
# Configuración Site24x7
# =========================
SITE24X7_BASE_URL = "https://www.site24x7.com/api"
CURRENT_STATUS_PATH = "/msp/customers/monitors/status"  # Customer Wise Monitor Status

AnyType = Any  # alias solo para tipado


# -----------------------------------
# Utilidades para extraer el token
# -----------------------------------
def collect_tokens(obj: Any) -> List[str]:
    """
    Recorre recursivamente un dict/list buscando posibles tokens
    en claves tipo 'access_token', 'token', etc.
    Devuelve una lista de tokens en el orden en que aparecen.
    """
    found: List[str] = []

    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(k, str):
                key_norm = k.strip().lower()
                if key_norm in {k.lower() for k in CANDIDATE_KEYS} and isinstance(v, str) and v.strip():
                    found.append(v.strip())
            found.extend(collect_tokens(v))

    elif isinstance(obj, list):
        for item in obj:
            found.extend(collect_tokens(item))

    return found


def get_site24x7_token() -> str:
    """
    Llama al webhook, parsea la respuesta y toma SIEMPRE el 3er token
    si hay 3 o más; si no, toma el último disponible.
    """
    headers = {HEADER_NAME: SECRET}
    req = urllib.request.Request(url=TOKEN_URL, method="GET", headers=headers)
    ctx = ssl.create_default_context() if VERIFY_SSL else ssl._create_unverified_context()

    try:
        with urllib.request.urlopen(req, timeout=20, context=ctx) as resp:
            status = resp.getcode()
            body = resp.read()
    except Exception as e:
        raise RuntimeError(f"Error al llamar al webhook de token: {e}")

    if status // 100 != 2:
        raise RuntimeError(f"Webhook de token respondió HTTP {status}")

    text = body.decode("utf-8", errors="replace").strip()

    # Intentar JSON primero
    try:
        data = json.loads(text)
        tokens = collect_tokens(data)
        if tokens:
            if len(tokens) >= 3:
                chosen = tokens[2]  # 3er token
            else:
                chosen = tokens[-1]  # el último disponible

            # guardar a archivo por compatibilidad
            try:
                TOKEN_FILE.write_text(chosen, encoding="utf-8")
            except Exception:
                pass

            return chosen

        # No se encontraron tokens explícitos, usar cuerpo tal cual
        if text:
            try:
                TOKEN_FILE.write_text(text, encoding="utf-8")
            except Exception:
                pass
            return text

        raise RuntimeError("No se encontró token en la respuesta del webhook.")

    except json.JSONDecodeError:
        # No era JSON, tratamos el cuerpo como token simple
        if not text:
            raise RuntimeError("Respuesta vacía del webhook de token.")
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
    Llama a /msp/customers/monitors/status y devuelve el bloque del cliente
    que corresponde al zaaid indicado.
    """
    headers = {
        "Accept": "application/json; version=2.0",
        "Authorization": f"Zoho-oauthtoken {access_token}",
    }

    url = f"{SITE24X7_BASE_URL}{CURRENT_STATUS_PATH}"
    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    # data["data"] es una lista de clientes, buscamos el zaaid
    customers = data.get("data", [])
    for customer in customers:
        if str(customer.get("zaaid")) == str(zaaid):
            return customer

    # Si no lo encontramos, devolvemos un dict vacío
    return {}


def build_counters(monitors: List[Dict[str, AnyType]]) -> Dict[str, int]:
    """
    A partir de la lista de monitores arma los contadores tipo:
    abajo, crítico, problema, arriba, suspendidos.
    Basado en el campo integer 'status'.
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
