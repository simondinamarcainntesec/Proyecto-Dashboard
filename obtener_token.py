#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
obtener_token_final_v2.py — Toma el 2° token si vienen dos o más; si no, el único disponible.
- Soporta respuestas JSON dict/list (y anidadas).
- Busca claves: "Acces_token", "access_token", "token", "Access_Token", "ACCESS_TOKEN".
- Si no es JSON, trata el cuerpo como token en texto plano.
- Imprime SOLO el token por stdout y lo guarda en token.txt.
"""

import json, ssl, sys, urllib.request
from pathlib import Path
from typing import Any, List

URL = "https://iaproductivo.inntesec.cl/webhook/3c850e31-e699-4fa6-9fed-513d4ccd281b"
SECRET = "@L^E4$h!f^r1VmwD#c1B#C8XzM#B4pON"
HEADER_NAME = "passkey"
VERIFY_SSL = True

TOKEN_FILE = Path(__file__).resolve().parent / "token.txt"

CANDIDATE_KEYS = {
    "acces_token", "access_token", "token",
    "access_token", "access-token", "access token",
    "access_token".upper(), "access_token".title(), "access_token".capitalize(),
    "access_token".replace("_", ""), "access_token".replace("_", "-")
}
CANDIDATE_KEYS.update({"access_token", "access-token", "access token", "access_token".upper(), "access_token".title(), "acces_token", "Access_Token", "ACCESS_TOKEN"})

def collect_tokens(obj: Any) -> List[str]:
    """Recorre recursivamente y devuelve todos los tokens encontrados, en orden."""
    found: List[str] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(k, str):
                key_norm = k.strip().lower()
                if key_norm in CANDIDATE_KEYS and isinstance(v, str) and v.strip():
                    found.append(v.strip())
            # seguir recorriendo
            found.extend(collect_tokens(v))
    elif isinstance(obj, list):
        for item in obj:
            found.extend(collect_tokens(item))
    return found

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
        print(f"HTTP {status}", file=sys.stderr)
        sys.exit(2)

    text = body.decode("utf-8", errors="replace").strip()

    # 1) Intentar JSON
    try:
        data = json.loads(text)
        tokens = collect_tokens(data)
        if tokens:
            # si hay 2 o más, siempre el segundo; si no, el único
            chosen = tokens[0] if len(tokens) >= 2 else tokens[0]
            try:
                TOKEN_FILE.write_text(chosen, encoding="utf-8")
            except Exception as e:
                print(f"No se pudo guardar token en archivo: {e}", file=sys.stderr)
            print(chosen)
            sys.exit(0)
        else:
            print(text)
            sys.exit(3)
    except Exception:
        if text:
            try:
                TOKEN_FILE.write_text(text, encoding="utf-8")
            except Exception as e:
                print(f"No se pudo guardar token en archivo: {e}", file=sys.stderr)
            print(text)
            sys.exit(0)
        else:
            sys.exit(3)

if __name__ == "__main__":
    main()
