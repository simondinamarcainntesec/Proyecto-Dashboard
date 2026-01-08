import json
import os
import ssl
import urllib.request
from pathlib import Path
from typing import Any, List, Dict

import requests

WEBHOOK_URL = os.environ.get("SITE24X7_WEBHOOK_URL", "").strip()
WEBHOOK_SECRET = os.environ.get("SITE24X7_WEBHOOK_SECRET", "") or ""
WEBHOOK_HEADER_NAME = os.environ.get("SITE24X7_WEBHOOK_HEADER_NAME", "passkey")

SITE24X7_BASE_URL = os.environ.get(
    "SITE24X7_API_BASE_URL",
    "https://www.site24x7.com/api",
).rstrip("/")

_raw_verify = (os.environ.get("SITE24X7_VERIFY_SSL", "True") or "").strip().lower()
VERIFY_SSL = _raw_verify in ("1", "true", "yes", "y", "on")

TOKEN_FILE = Path(__file__).resolve().parent / "token.txt"

AnyType = Any

CURRENT_STATUS_PATH = "/msp/customers/monitors/status"
ANOMALY_DASHBOARD_PATH = "/reports/anomaly"
ANOMALY_MONITOR_PATH = "/reports/anomaly/monitors/type"

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

    try:
        data = json.loads(text)
        tokens = collect_tokens(data)

        if not tokens:
            raise RuntimeError("No se encontraron tokens en el JSON del webhook.")

        chosen = tokens[2] if len(tokens) >= 3 else tokens[-1]

        try:
            TOKEN_FILE.write_text(chosen, encoding="utf-8")
        except Exception:
            pass

        return chosen

    except json.JSONDecodeError:
        if not text:
            raise RuntimeError("Respuesta vacía del webhook de token (no es JSON).")
        try:
            TOKEN_FILE.write_text(text, encoding="utf-8")
        except Exception:
            pass
        return text


def fetch_customer_status(access_token: str, zaaid: str) -> Dict[str, AnyType]:
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

    return {}


def build_counters(monitors: List[Dict[str, AnyType]]) -> Dict[str, int]:
    counters = {
        "down": 0,
        "up": 0,
        "trouble": 0,
        "critical": 0,
        "suspended": 0,
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


def fetch_anomaly_summary(
    access_token: str,
    zaaid: str,
    period: int = 3,
    monitor_type: str | None = None,
    start_ms: int | None = None,
    end_ms: int | None = None,
) -> Dict[str, AnyType]:
    headers = {
        "Accept": "application/json; version=2.0",
        "Authorization": f"Zoho-oauthtoken {access_token}",
    }

    # (Opcional pero recomendado en MSP) refuerza el contexto del customer
    if zaaid:
        headers["Cookie"] = f"zaaid={zaaid}"

    params: Dict[str, AnyType] = {
        "period": int(period),
        "zaaid": zaaid,
    }

    if monitor_type:
        params["monitor_type"] = monitor_type

    # Solo para periodo personalizado
    if int(period) == 50 and start_ms and end_ms:
        params["start_time"] = int(start_ms)
        params["end_time"] = int(end_ms)

    url = f"{SITE24X7_BASE_URL}{ANOMALY_DASHBOARD_PATH}"
    resp = requests.get(url, headers=headers, params=params, timeout=30)

    if resp.status_code != 200:
        raise RuntimeError(
            f"Site24x7 /reports/anomaly devolvió {resp.status_code}: {resp.text}"
        )

    data = resp.json()
    return (data.get("data") or {}).get("anomaly_summary") or {}



def fetch_anomaly_by_monitor(
    access_token: str,
    monitor_id: str,
    zaaid: str,
    period: int = 5,
    severity: str = "CONFIRMED,LIKELY,INFO",
    start_ms: int | None = None,
    end_ms: int | None = None,
) -> Dict[str, AnyType]:
    headers = {
        "Accept": "application/json; version=2.0",
        "Authorization": f"Zoho-oauthtoken {access_token}",
    }

    if zaaid:
        headers["Cookie"] = f"zaaid={zaaid}"

    params: Dict[str, AnyType] = {
        "monitor_id": monitor_id,
        "period": period,
        "severity": severity,
    }

    if start_ms and end_ms:
        params["start_time"] = int(start_ms)
        params["end_time"] = int(end_ms)

    url = f"{SITE24X7_BASE_URL}{ANOMALY_MONITOR_PATH}"
    resp = requests.get(url, headers=headers, params=params, timeout=30)

    if resp.status_code != 200:
        raise RuntimeError(
            f"Site24x7 {ANOMALY_MONITOR_PATH} devolvió {resp.status_code}: {resp.text}"
        )

    return (resp.json() or {}).get("data") or {}
