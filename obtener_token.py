#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
obtener_token_final_v2.py — Header `passkey: <clave>` y extracción robusta del token.
- Soporta respuestas JSON tipo dict o list (y anidadas).
- Busca claves comunes: "Acces_token", "access_token", "token" en cualquier nivel.
- Imprime SOLO el token por stdout si encuentra uno.
- Guarda el token en `token.txt`.
"""

import json, ssl, sys, urllib.request
from pathlib import Path
from typing import Any, Optional

URL = "https://iaproductivo.inntesec.cl/webhook/3c850e31-e699-4fa6-9fed-513d4ccd281b"
SECRET = "@L^E4$h!f^r1VmwD#c1B#C8XzM#B4pON"
HEADER_NAME = "passkey"
VERIFY_SSL = True

TOKEN_FILE = Path(__file__).resolve().parent / "token.txt"

CANDIDATE_KEYS = {"Acces_token", "access_token", "token", "Access_Token", "ACCESS_TOKEN"}

def find_token(obj: Any) -> Optional[str]:
    if isinstance(obj, dict):
        for k in obj.keys():
            if isinstance(k, str) and k in CANDIDATE_KEYS:
                v = obj[k]
                if isinstance(v, str) and v.strip():
                    return v.strip()
        for v in obj.values():
            t = find_token(v)
            if t:
                return t
    elif isinstance(obj, list):
        for item in obj:
            t = find_token(item)
            if t:
                return t
    return None

def main():
    if "TU-N8N" in URL or "XXXXXXXX" in URL:
        sys.exit(1)  # URL no configurada

    headers = {HEADER_NAME: SECRET}
    req = urllib.request.Request(url=URL, method="GET", headers=headers)
    ctx = ssl.create_default_context() if VERIFY_SSL else ssl._create_unverified_context()

    try:
        with urllib.request.urlopen(req, timeout=20, context=ctx) as resp:
            status = resp.getcode()
            body = resp.read()
    except Exception as e:
        print(f"Error al llamar la API: {e}", file=sys.stderr)
        sys.exit(2)

    if status // 100 != 2:
        sys.exit(2)

    text = body.decode("utf-8", errors="replace").strip()
    try:
        data = json.loads(text)
    except Exception:
        # No es JSON, podría ser token en texto plano
        if text:
            token = text
            TOKEN_FILE.write_text(token, encoding="utf-8")
            print(token)
            sys.exit(0)
        sys.exit(3)

    token = find_token(data)
    if token:
        # Guardar en archivo
        try:
            TOKEN_FILE.write_text(token, encoding="utf-8")
        except Exception as e:
            print(f"No se pudo guardar token en archivo: {e}", file=sys.stderr)
        # Imprimir por stdout
        print(token)
        sys.exit(0)
    else:
        # como último recurso, imprimir JSON completo
        print(text)
        sys.exit(3)

if __name__ == "__main__":
    main()
