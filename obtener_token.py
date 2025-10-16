#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
obtener_token_final_v2.py — Header `passkey: <clave>` y extracción robusta del token.
- Soporta respuestas JSON tipo dict o list (y anidadas).
- Busca claves comunes: "Acces_token", "access_token", "token" en cualquier nivel.
- Imprime SOLO el token por stdout si encuentra uno.
"""

import json, ssl, sys, urllib.request
from typing import Any, Optional

# ==== CONFIGURA ESTO ====
URL = "https://iaproductivo.inntesec.cl/webhook/3c850e31-e699-4fa6-9fed-513d4ccd281b"   # <-- pega la URL real
SECRET = "@L^E4$h!f^r1VmwD#c1B#C8XzM#B4pON"                # <-- pega tu clave (sin JSON)
HEADER_NAME = "passkey"                   # según el método 6 que funcionó
VERIFY_SSL = True
# ========================

CANDIDATE_KEYS = {"Acces_token", "access_token", "token", "Access_Token", "ACCESS_TOKEN"}

def find_token(obj: Any) -> Optional[str]:
    """
    Busca token en cualquier estructura (dict/list), recorriendo recursivamente.
    Devuelve el primer string no vacío encontrado para las claves candidatas.
    """
    if isinstance(obj, dict):
        # chequeo directo de claves
        for k in list(obj.keys()):
            if isinstance(k, str) and k in CANDIDATE_KEYS:
                v = obj[k]
                if isinstance(v, str) and v.strip():
                    return v.strip()
        # recorrer valores
        for v in obj.values():
            t = find_token(v)
            if t:
                return t
        return None
    elif isinstance(obj, list):
        for item in obj:
            t = find_token(item)
            if t:
                return t
        return None
    else:
        return None

def main():
    if "TU-N8N" in URL or "XXXXXXXX" in URL:
        # URL sin configurar
        sys.exit(1)

    headers = {HEADER_NAME: SECRET}
    req = urllib.request.Request(url=URL, method="GET", headers=headers)
    ctx = ssl.create_default_context() if VERIFY_SSL else ssl._create_unverified_context()

    try:
        with urllib.request.urlopen(req, timeout=20, context=ctx) as resp:
            status = resp.getcode()
            body = resp.read()
    except Exception:
        sys.exit(2)

    if status // 100 != 2:
        sys.exit(2)

    # Intentar parsear JSON
    text = body.decode("utf-8", errors="replace").strip()
    try:
        data = json.loads(text)
    except Exception:
        # Si no es JSON, imprime el cuerpo tal cual (por si es un token en texto plano)
        if text:
            print(text)
            sys.exit(0)
        sys.exit(3)

    token = find_token(data)
    if token:
        print(token)
        sys.exit(0)
    else:
        # como último recurso, imprime el JSON completo (podría ser útil para pipelines)
        print(text)
        sys.exit(3)

if __name__ == "__main__":
    main()