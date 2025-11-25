# siem/log360_service.py
import json
import ssl
import urllib.request
from datetime import date
from typing import Any, List, Optional, Tuple

import requests

# ============================================================
# 🧩 CONFIG WEBHOOK TOKEN (misma lógica que obtener_token_final_v2.py)
# ============================================================

URL_WEBHOOK = "https://iaproductivo.inntesec.cl/webhook/3c850e31-e699-4fa6-9fed-513d4ccd281b"
SECRET = "@L^E4$h!f^r1VmwD#c1B#C8XzM#B4pON"
HEADER_NAME = "passkey"
VERIFY_SSL = True

# CANDIDATE_KEYS igual que en tu script
CANDIDATE_KEYS = {
    "acces_token", "access_token", "token",
    "access_token", "access-token", "access token",
    "access_token".upper(), "access_token".title(), "access_token".capitalize(),
    "access_token".replace("_", ""), "access_token".replace("_", "-")
}
CANDIDATE_KEYS.update({
    "access_token",
    "access-token",
    "access token",
    "access_token".upper(),
    "access_token".title(),
    "acces_token",
    "Access_Token",
    "ACCESS_TOKEN",
})


def collect_tokens(obj: Any) -> List[str]:
    """
    Misma función que en obtener_token_final_v2.py:
    recorre recursivamente y devuelve todos los tokens encontrados, en orden.
    """
    found: List[str] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(k, str):
                key_norm = k.strip().lower()
                if key_norm in {k2.lower() for k2 in CANDIDATE_KEYS} and isinstance(v, str) and v.strip():
                    found.append(v.strip())
            # seguir recorriendo
            found.extend(collect_tokens(v))
    elif isinstance(obj, list):
        for item in obj:
            found.extend(collect_tokens(item))
    return found


def obtener_token_logs360() -> Tuple[Optional[str], Optional[str]]:
    """
    Versión "función" de tu script obtener_token_final_v2.py.

    - Llama al webhook n8n con el header passkey.
    - Si la respuesta es JSON, busca todas las claves candidatas y:
        * Si hay 2+ tokens -> usa SIEMPRE el segundo (Logs360).
        * Si hay 1 token  -> usa ese único.
    - Si no es JSON pero hay texto -> usa el cuerpo como token.
    - NO escribe ni lee token.txt, solo trabaja en memoria.

    Retorna:
        (token, None) si todo bien
        (None, "mensaje de error") si algo falla
    """
    if "TU-N8N" in URL_WEBHOOK or "XXXXXXXX" in URL_WEBHOOK:
        return None, "URL_WEBHOOK no configurada en el script."

    headers = {HEADER_NAME: SECRET}
    ctx = ssl.create_default_context() if VERIFY_SSL else ssl._create_unverified_context()
    req = urllib.request.Request(url=URL_WEBHOOK, method="GET", headers=headers)

    try:
        with urllib.request.urlopen(req, timeout=20, context=ctx) as resp:
            status = resp.getcode()
            body = resp.read()
    except Exception as e:
        return None, f"Error al llamar la API del webhook: {e}"

    if status // 100 != 2:
        texto = body.decode("utf-8", errors="replace")
        return None, f"HTTP {status} al llamar webhook. Cuerpo: {texto}"

    text = body.decode("utf-8", errors="replace").strip()

    # 1) Intentar JSON (igual que tu script)
    try:
        data = json.loads(text)
        tokens = collect_tokens(data)

        print("=== TOKENS ENCONTRADOS EN WEBHOOK ===")
        if not tokens:
            print("(ninguno)")
        else:
            for idx, tk in enumerate(tokens, start=1):
                print(f"  {idx}) {tk[:20]}... (largo={len(tk)})")
        print("======================================")

        if tokens:
            # si hay 2 o más, siempre el segundo; si no, el único
            chosen = tokens[1] if len(tokens) >= 2 else tokens[0]
            print(f"[INFO] Token Logs360 elegido empieza con: {chosen[:20]}...")
            return chosen, None

        # Si no hay tokens, pero sí texto, tu script imprime text y sale con código 3.
        # Aquí devolvemos error explícito.
        if text:
            return None, "No se encontraron tokens en el JSON del webhook."
        return None, "No se encontró token en el JSON y el cuerpo está vacío."

    except Exception:
        # 2) No es JSON → usar el cuerpo como token (igual que tu script)
        if text:
            print("[WARN] La respuesta del webhook NO es JSON válido. Se usa el cuerpo como token.")
            print(text[:200])
            return text, None

        return None, "La respuesta del webhook no es JSON y está vacía."


# ============================================================
# 🧩 CONFIG LOG360 ALERTS
# ============================================================

BASE_URL = "https://log360cloud.manageengine.com/api/v2"
DEFAULT_ACCOUNT_ID = "897671591"  # Inntesec Lab (fallback si el tenant no trae nada)
PAGE_LIMIT = 1000
MAX_ALERTS = 10000


def _build_range(from_date: date, to_date: date) -> Tuple[str, str]:
    """
    Construye start_time / end_time en formato ISO8601 con 'Z',
    igual que el cURL que tú probaste:

    start_time = YYYY-MM-DDT00:00:00Z
    end_time   = YYYY-MM-DDT23:59:59Z
    """
    start_time = f"{from_date.isoformat()}T00:00:00Z"
    end_time = f"{to_date.isoformat()}T23:59:59Z"
    return start_time, end_time


def obtener_alertas_logs360(
    query: str = "",
    account_id: str = "",
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
) -> Tuple[list, Optional[str], str, str, str]:
    """
    Devuelve (lista_alertas, error_msg, start_time, end_time, acc_id_usado).

    - Usa el token obtenido desde el webhook (2º token = Logs360) EN MEMORIA,
      con la misma lógica de tu script.
    - Usa el account_id del tenant (logs360siem_id); si viene vacío, usa DEFAULT_ACCOUNT_ID.
    - Aplica rango de fechas from/to y construye:
        start_time = YYYY-MM-DDT00:00:00Z
        end_time   = YYYY-MM-DDT23:59:59Z
    - Pagina en bloques de PAGE_LIMIT hasta llegar a MAX_ALERTS o no haya más datos.
    """

    # 1) Token desde webhook (misma lógica que obtener_token_final_v2.py)
    token, err_token = obtener_token_logs360()
    if not token:
        return [], f"No se pudo obtener token: {err_token or 'desconocido'}", "", "", ""

    # 2) Fechas
    today = date.today()
    if to_date is None:
        to_date = today
    if from_date is None:
        from_date = to_date  # por defecto, solo el día seleccionado

    start_time, end_time = _build_range(from_date, to_date)

    # 3) Account ID (desde tenant o fallback)
    acc_id = (account_id or "").strip() or DEFAULT_ACCOUNT_ID

    print("========== SIEM / Django ==========")
    print(f"[SIEM] Account ID      : {acc_id}")
    print(f"[SIEM] Token (inicio)  : {token[:30]}...")
    print(f"[SIEM] Query           : {query!r}")
    print(f"[SIEM] Rango (form)    : {from_date} -> {to_date}")
    print(f"[SIEM] Rango UTC (Z)   : {start_time} -> {end_time}")
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

        # por debug, ver parte del body bruto
        try:
            print(f"[SIEM] /alerts raw body   : {resp.text[:500]}")
        except Exception:
            pass

        if resp.status_code // 100 != 2:
            return todos, f"HTTP {resp.status_code} al llamar /alerts: {resp.text}", start_time, end_time, acc_id

        try:
            data = resp.json()
        except ValueError:
            return todos, f"La respuesta de /alerts no es JSON: {resp.text[:1000]}", start_time, end_time, acc_id

        if "error" in data:
            err_txt = json.dumps(data, ensure_ascii=False)
            print(f"[SIEM] /alerts JSON error : {err_txt}")
            return todos, err_txt, start_time, end_time, acc_id

        batch = data.get("data") or []
        if not isinstance(batch, list):
            return todos, f"Estructura inesperada de /alerts: {json.dumps(data, ensure_ascii=False)[:1000]}", start_time, end_time, acc_id

        todos.extend(batch)

        if len(batch) < PAGE_LIMIT:
            break
        if len(todos) >= MAX_ALERTS:
            break

        current_from += PAGE_LIMIT

    return todos, None, start_time, end_time, acc_id
