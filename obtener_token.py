#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
obtener_token.py — Extrae tokens desde un webhook y permite elegir cuál devolver.

- Soporta respuestas JSON dict/list (y anidadas).
- Busca claves tipo: acces_token/access_token/token/access-token/access token/Access_Token/ACCESS_TOKEN.
- Si no es JSON, trata el cuerpo como texto plano.
- Si en un campo hay "TOKEN1  TOKEN2" (dos espacios o varios), se separa por whitespace.
- Imprime SOLO el token seleccionado por stdout y lo guarda en token.txt.

ENV requeridas:
  - LOG360_WEBHOOK_URL
  - LOG360_WEBHOOK_SECRET

Selección del token (orden de preferencia):
  1) CLI: --index (0-based) o --n (1-based) o --service alarmsone|logs360|site24x7
  2) ENV: WEBHOOK_TOKEN_INDEX (0-based) o WEBHOOK_TOKEN_N (1-based) o WEBHOOK_TOKEN_SERVICE
  3) Default: index 0 (primer token)

Ejemplos:
  python3 obtener_token.py                 -> primer token
  python3 obtener_token.py --index 1       -> segundo token
  python3 obtener_token.py --n 2           -> segundo token
  python3 obtener_token.py --service logs360 -> segundo token (mapa por servicio)
"""

import argparse
import json
import os
import ssl
import sys
import urllib.request
from pathlib import Path
from typing import Any, List, Optional, Tuple

# ✅ Variables de entorno requeridas
URL = (os.getenv("LOG360_WEBHOOK_URL") or "").strip()
SECRET = (os.getenv("LOG360_WEBHOOK_SECRET") or "").strip()

HEADER_NAME = "passkey"
VERIFY_SSL = True

TOKEN_FILE = Path(__file__).resolve().parent / "token.txt"

CANDIDATE_KEYS = {
    "acces_token",
    "access_token",
    "token",
    "access-token",
    "access token",
    "Access_Token",
    "ACCESS_TOKEN",
    "access_token".upper(),
    "access_token".title(),
    "access_token".capitalize(),
    "access_token".replace("_", ""),
    "access_token".replace("_", "-"),
}
CANDIDATE_KEYS_LOWER = {k.lower() for k in CANDIDATE_KEYS}

# Mapa por servicio (0-based)
SERVICE_INDEX = {
    "alarmsone": 0,
    "logs360": 1,
    "site24x7": 2,
}


def _split_tokens(s: str) -> List[str]:
    """
    Separa tokens por whitespace (maneja 2 espacios o más).
    """
    raw = (s or "").strip()
    if not raw:
        return []
    # split() colapsa múltiples espacios, tabs y saltos de línea
    return [p.strip() for p in raw.split() if p.strip()]


def collect_tokens(obj: Any) -> List[str]:
    """
    Recorre recursivamente y devuelve todos los tokens encontrados, en orden.
    Si el valor trae varios tokens en un string (ej: "t1  t2"), los separa.
    """
    found: List[str] = []

    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(k, str):
                key_norm = k.strip().lower()
                if key_norm in CANDIDATE_KEYS_LOWER and isinstance(v, str) and v.strip():
                    found.extend(_split_tokens(v))
            found.extend(collect_tokens(v))

    elif isinstance(obj, list):
        for item in obj:
            found.extend(collect_tokens(item))

    return found


def _resolve_desired_index(args: argparse.Namespace) -> int:
    """
    Devuelve índice 0-based del token deseado.
    Orden:
      - CLI --service / --index / --n
      - ENV WEBHOOK_TOKEN_SERVICE / WEBHOOK_TOKEN_INDEX / WEBHOOK_TOKEN_N
      - default 0
    """
    # 1) CLI
    if args.service:
        return SERVICE_INDEX.get(args.service.lower(), 0)

    if args.index is not None:
        return max(0, int(args.index))

    if args.n is not None:
        return max(0, int(args.n) - 1)

    # 2) ENV
    env_service = (os.getenv("WEBHOOK_TOKEN_SERVICE") or "").strip().lower()
    if env_service:
        return SERVICE_INDEX.get(env_service, 0)

    env_index = os.getenv("WEBHOOK_TOKEN_INDEX")
    if env_index is not None and str(env_index).strip() != "":
        try:
            return max(0, int(str(env_index).strip()))
        except Exception:
            return 0

    env_n = os.getenv("WEBHOOK_TOKEN_N")
    if env_n is not None and str(env_n).strip() != "":
        try:
            return max(0, int(str(env_n).strip()) - 1)
        except Exception:
            return 0

    # 3) default
    return 0


def _fetch_webhook_text() -> str:
    if not URL:
        raise RuntimeError("Falta LOG360_WEBHOOK_URL en el entorno.")
    if not SECRET:
        raise RuntimeError("Falta LOG360_WEBHOOK_SECRET en el entorno.")

    # placeholders típicos
    if ("TU-N8N" in URL) or ("XXXXXXXX" in URL):
        raise RuntimeError("LOG360_WEBHOOK_URL no configurada (placeholder detectado).")

    headers = {HEADER_NAME: SECRET}
    req = urllib.request.Request(url=URL, method="GET", headers=headers)
    ctx = ssl.create_default_context() if VERIFY_SSL else ssl._create_unverified_context()

    with urllib.request.urlopen(req, timeout=20, context=ctx) as resp:
        status = resp.getcode()
        body = resp.read()

    if status // 100 != 2:
        raise RuntimeError(f"Webhook respondió HTTP {status}")

    text = (body.decode("utf-8", errors="replace") or "").strip()
    if not text:
        raise RuntimeError("Respuesta vacía del webhook.")
    return text


def _extract_tokens_from_text(text: str) -> List[str]:
    # Intentar JSON
    try:
        data = json.loads(text)
        tokens = collect_tokens(data)
        if tokens:
            return tokens
    except Exception:
        pass

    # Fallback: texto plano (puede traer varios tokens separados por espacios)
    return _split_tokens(text)


def main() -> None:
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument("--index", type=int, default=None, help="Índice 0-based del token a devolver (0=primero, 1=segundo, ...)")
    parser.add_argument("--n", type=int, default=None, help="Número 1-based del token a devolver (1=primero, 2=segundo, ...)")
    parser.add_argument("--service", type=str, default=None, help="Alias de servicio: alarmsone|logs360|site24x7")
    args = parser.parse_args()

    desired_index = _resolve_desired_index(args)

    try:
        text = _fetch_webhook_text()
        tokens = _extract_tokens_from_text(text)

        if not tokens:
            print("No se encontraron tokens en la respuesta del webhook.", file=sys.stderr)
            sys.exit(3)

        # Selección por índice, con fallback al último si se pasa del rango
        if desired_index < len(tokens):
            chosen = tokens[desired_index]
        else:
            chosen = tokens[-1]

        chosen = (chosen or "").strip()
        if not chosen:
            print("El token seleccionado está vacío.", file=sys.stderr)
            sys.exit(3)

        try:
            TOKEN_FILE.write_text(chosen, encoding="utf-8")
        except Exception as e:
            print(f"No se pudo guardar token en archivo: {e}", file=sys.stderr)

        sys.stdout.write(chosen + "\n")
        sys.exit(0)

    except Exception as e:
        print(str(e), file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
