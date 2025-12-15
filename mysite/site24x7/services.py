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

# ============================================================
# Constantes de paths de API
# ============================================================

# Customer Wise Monitor Status
CURRENT_STATUS_PATH = "/msp/customers/monitors/status"

# Anomaly Dashboard (resumen por monitor / monitor groups)
ANOMALY_DASHBOARD_PATH = "/reports/anomaly"

# Anomaly Report por monitor
ANOMALY_MONITOR_PATH = "/reports/anomaly/monitors/type"
# (Si en el futuro usas por grupo, sería /reports/anomaly/monitor_groups)


# ============================================================
# Claves posibles donde puede venir el token en el JSON del webhook
# ============================================================

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
    "access_token".replace("_", ""),   # accesstoken
    "access_token".replace("_", "-"),  # access-token
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


# ============================================================
# Utilidades para extraer el token desde el webhook (n8n)
# ============================================================

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

    Se puede reutilizar tanto para Monitors como para Anomalies.
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


# ============================================================
# Monitores – Customer Wise Monitor Status
# (por si lo quieres usar desde otros módulos)
# ============================================================

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

    status:
      0 → down
      1 → up
      2 → trouble
      3 → critical
      5 → suspended
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


# ============================================================
# Anomalías – resumen y detalle (con ZAAID MSP)
# ============================================================

def fetch_anomaly_summary(
    access_token: str,
    zaaid: str,
    period: int = 3,
    monitor_type: str | None = None,
) -> Dict[str, AnyType]:
    """
    Llama a /reports/anomaly y devuelve el bloque anomaly_summary.

    IMPORTANTE: en modo MSP hay que pasar zaaid.
    """
    headers = {
        "Accept": "application/json; version=2.0",
        "Authorization": f"Zoho-oauthtoken {access_token}",
    }

    params: Dict[str, AnyType] = {
        "period": period,
        "zaaid": zaaid,  # <- clave para MSP
    }
    if monitor_type:
        params["monitor_type"] = monitor_type

    url = f"{SITE24X7_BASE_URL}{ANOMALY_DASHBOARD_PATH}"
    resp = requests.get(url, headers=headers, params=params, timeout=30)

    if resp.status_code != 200:
        raise RuntimeError(
            f"Site24x7 /reports/anomaly devolvió {resp.status_code}: {resp.text}"
        )

    data = resp.json()
    # La doc dice que viene dentro de data.anomaly_summary
    return (data.get("data") or {}).get("anomaly_summary") or {}


def fetch_anomaly_by_monitor(
    access_token: str,
    zaaid: str,
    monitor_id: str,
    period: int = 3,
    severity: str = "CONFIRMED,LIKELY,INFO",
) -> Dict[str, AnyType]:
    """
    Llama a /reports/anomaly/monitors/type para un monitor específico.

    Devuelve el 'data' completo:
      - anomaly_table_data (detalle)
      - anomaly_chart_data (serie para gráficos)

    También incluye zaaid porque estamos en modo MSP.
    """
    headers = {
        "Accept": "application/json; version=2.0",
        "Authorization": f"Zoho-oauthtoken {access_token}",
    }

    params = {
        "monitor_id": monitor_id,
        "period": period,
        "severity": severity,  # CSV con CONFIRMED,LIKELY,INFO, etc.
        "zaaid": zaaid,        # <- clave para MSP
    }

    url = f"{SITE24X7_BASE_URL}{ANOMALY_MONITOR_PATH}"
    resp = requests.get(url, headers=headers, params=params, timeout=30)

    if resp.status_code != 200:
        raise RuntimeError(
            f"Site24x7 /reports/anomaly/monitors/type devolvió {resp.status_code}: {resp.text}"
        )

    return resp.json().get("data") or {}
