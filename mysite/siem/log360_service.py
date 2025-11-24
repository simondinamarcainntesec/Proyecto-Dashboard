# siem/log360_service.py
import json
import ssl
import urllib.request
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any, List, Tuple, Optional

import requests
from django.conf import settings  # por si luego quieres usar settings


# ================== CONFIG WEBHOOK TOKEN ==================

URL_WEBHOOK = "https://iaproductivo.inntesec.cl/webhook/3c850e31-e699-4fa6-9fed-513d4ccd281b"
SECRET = "@L^E4$h!f^r1VmwD#c1B#C8XzM#B4pON"
HEADER_NAME = "passkey"
VERIFY_SSL = True

TOKEN_FILE = Path(__file__).resolve().parent / "token.txt"

# Mismas claves candidatas que en tu siem.py que funciona
CANDIDATE_KEYS = {
    "acces_token",
    "access_token",
    "token",
    "access-token",
    "access token",
    "access_token",
    "access_token".upper(),   # ACCESS_TOKEN
    "access_token".title(),   # Access_Token (aprox)
    "access_token".replace("_", ""),   # accesstoken
    "access_token".replace("_", "-"),  # access-token
    "Access_Token",
    "ACCESS_TOKEN",
}

# ================== CONFIG LOG360 ALERTS ==================

BASE_URL = "https://log360cloud.manageengine.com/api/v2"
ACCOUNT_ID = "897671591"  # Inntesec Lab

MAX_ALERTS = 10000
PAGE_LIMIT = 1000  # por página


# ---- helpers token ----

def _collect_tokens(obj: Any) -> List[str]:
    """
    Recorre recursivamente un dict/list y devuelve todos los tokens encontrados, en orden.
    (Misma lógica que collect_tokens de tu script siem.py)
    """
    found: List[str] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(k, str):
                key_norm = k.strip().lower()
                if key_norm in {s.lower() for s in CANDIDATE_KEYS} and isinstance(v, str) and v.strip():
                    found.append(v.strip())
            found.extend(_collect_tokens(v))
    elif isinstance(obj, list):
        for item in obj:
            found.extend(_collect_tokens(item))
    return found


def obtener_token_logs360() -> Tuple[Optional[str], Optional[str]]:
    """
    Devuelve (token_logs360, error_msg) usando SIEMPRE el webhook n8n.

    - Si el JSON trae 2 tokens:
        1) AlarmsOne
        2) Logs360  -> ESTE es el que se usará.
      Siempre se toma tokens[1].
    - Si solo hay 1 token, se usa ese.
    - Si no es JSON, se usa el cuerpo completo como token.
    """
    if "TU-N8N" in URL_WEBHOOK or "XXXXXXXX" in URL_WEBHOOK:
        return None, "URL_WEBHOOK no configurada en el script."

    headers = {HEADER_NAME: SECRET}
    req = urllib.request.Request(url=URL_WEBHOOK, method="GET", headers=headers)
    ctx = ssl.create_default_context() if VERIFY_SSL else ssl._create_unverified_context()

    try:
        with urllib.request.urlopen(req, timeout=20, context=ctx) as resp:
            status = resp.getcode()
            body = resp.read()
    except Exception as e:
        return None, f"Error al llamar la API del webhook: {e}"

    if status // 100 != 2:
        cuerpo = body.decode("utf-8", errors="replace")
        return None, f"HTTP {status} al llamar webhook. Cuerpo: {cuerpo}"

    text = body.decode("utf-8", errors="replace").strip()

    # 1) Intentar JSON (igual que en tu script siem.py)
    try:
        data = json.loads(text)

        tokens = _collect_tokens(data)

        # DEBUG opcional
        print("=== TOKENS ENCONTRADOS EN WEBHOOK ===")
        if not tokens:
            print("(ninguno)")
        else:
            for idx, tk in enumerate(tokens, start=1):
                print(f"  {idx}) {tk[:20]}... (largo={len(tk)})")
        print("======================================")

        if tokens:
            # Si hay 2 o más, SIEMPRE usamos el 2° (Logs360)
            if len(tokens) >= 2:
                chosen = tokens[1]
                print("[INFO] Usando SIEMPRE el 2° token como Logs360 (idx=2)")
            else:
                chosen = tokens[0]
                print("[INFO] Solo hay 1 token, se usa el único disponible")

            # Guardar por si quieres revisarlo en disco
            try:
                TOKEN_FILE.write_text(chosen, encoding="utf-8")
            except Exception:
                pass

            print(f"[INFO] Token Logs360 elegido empieza con: {chosen[:20]}...")
            return chosen, None

        # No se encontraron claves de token en el JSON
        if text:
            return None, "No se encontró ningún token en el JSON del webhook."
        return None, "No se encontró token en el JSON y el cuerpo está vacío."

    except Exception:
        # 2) No es JSON → usar el cuerpo como token (misma lógica que tu script)
        if text:
            print("[WARN] La respuesta del webhook NO es JSON válido. Se usa el cuerpo como token.")
            print(text[:200])
            try:
                TOKEN_FILE.write_text(text, encoding="utf-8")
            except Exception:
                pass
            return text, None

        return None, "La respuesta del webhook no es JSON y está vacía."


# ---- helpers rango de tiempo ----

def rango_ultimas_48h_utc() -> tuple[str, str]:
    """
    Rango tipo:
      start_time = Ayer 00:00:00 UTC
      end_time   = Hoy 23:59:59 UTC

    Es el mismo patrón que usaste a mano:
      "YYYY-MM-DDT00:00:00Z" -> "YYYY-MM-(DD+1)T23:59:59Z"
    pero calculado dinámicamente según la fecha actual UTC.
    """
    hoy_utc = datetime.now(timezone.utc).date()
    ayer_utc = hoy_utc - timedelta(days=1)

    inicio = datetime.combine(ayer_utc, time(0, 0, 0, tzinfo=timezone.utc))
    fin = datetime.combine(hoy_utc, time(23, 59, 59, tzinfo=timezone.utc))

    start_time = inicio.strftime("%Y-%m-%dT%H:%M:%SZ")
    end_time = fin.strftime("%Y-%m-%dT%H:%M:%SZ")
    return start_time, end_time


# ---- fetch alerts paginando ----

def obtener_alertas_logs360(query: str = "") -> Tuple[list, Optional[str], str, str]:
    """
    Devuelve (lista_alertas, error_msg, start_time, end_time).

    Trae TODAS las alertas de las últimas ~48 h:
      - start_time: ayer 00:00 UTC
      - end_time:   hoy 23:59:59 UTC
    paginando en bloques de PAGE_LIMIT.
    """
    token, err_token = obtener_token_logs360()
    if not token:
        return [], f"No se pudo obtener token: {err_token or 'desconocido'}", "", ""

    # Rango dinámico: últimas ~48h en UTC
    start_time, end_time = rango_ultimas_48h_utc()

    headers = {
        "Authorization": f"Zoho-oauthtoken {token}",
        "account_id": ACCOUNT_ID,
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
            "limit": PAGE_LIMIT,   # p.ej. 1000; definido arriba
            "response_type": "client",
        }

        try:
            resp = requests.post(
                f"{BASE_URL}/alerts",
                headers=headers,
                json=body,
                timeout=30,
            )
        except requests.RequestException as e:
            return todos, f"Error de red al llamar /alerts: {e}", start_time, end_time

        if resp.status_code // 100 != 2:
            return todos, f"HTTP {resp.status_code} al llamar /alerts: {resp.text}", start_time, end_time

        try:
            data = resp.json()
        except ValueError:
            return todos, f"La respuesta de /alerts no es JSON: {resp.text[:1000]}", start_time, end_time

        if "error" in data:
            # Por ej: {"error":{"code":"10001015","title":"Forbidden"}}
            return todos, json.dumps(data, ensure_ascii=False), start_time, end_time

        batch = data.get("data") or []
        if not isinstance(batch, list):
            return todos, f"Estructura inesperada de /alerts: {json.dumps(data, ensure_ascii=False)[:1000]}", start_time, end_time

        todos.extend(batch)

        # Si viene menos que PAGE_LIMIT, ya no hay más páginas
        if len(batch) < PAGE_LIMIT:
            break

        # Protección para no traer infinito
        if len(todos) >= MAX_ALERTS:
            break

        current_from += PAGE_LIMIT

    return todos, None, start_time, end_time
