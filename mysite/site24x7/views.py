# site24x7/views.py
import json
import os
import ssl
import urllib.request
from pathlib import Path
from typing import Any, List, Dict
from datetime import datetime

import requests
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils import timezone

from tenants.decorators import tenant_required
from tenants.models import Tenant, TenantUser, TenantDashboardEmbed

import logging

logger = logging.getLogger(__name__)

# =========================
# Config webhook Site24x7 (variables de entorno)
# =========================
SITE24X7_WEBHOOK_URL = os.environ.get("SITE24X7_WEBHOOK_URL")
SITE24X7_WEBHOOK_SECRET = os.environ.get("SITE24X7_WEBHOOK_SECRET")
SITE24X7_WEBHOOK_HEADER_NAME = os.environ.get("SITE24X7_WEBHOOK_HEADER_NAME", "passkey")

_raw_verify = (os.environ.get("SITE24X7_VERIFY_SSL", "True") or "").strip().lower()
SITE24X7_VERIFY_SSL = _raw_verify in ("1", "true", "yes", "y", "on")

TOKEN_FILE = Path(__file__).resolve().parent / "token.txt"

# Conjunto de claves candidato (alineado con tu script debug)
CANDIDATE_KEYS = {
    "acces_token",
    "access_token",
    "token",
    "access-token",
    "access token",
    "access_token".upper(),
    "access_token".title(),
    "access_token".capitalize(),
    "access_token".replace("_", ""),   # accesstoken -> para AccessToken
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

# =========================
# Config Site24x7 API (variables de entorno)
# =========================
SITE24X7_API_BASE_URL = os.environ.get("SITE24X7_API_BASE_URL", "https://www.site24x7.com/api")
CURRENT_STATUS_PATH = "/msp/customers/monitors/status"

# Preferencias de países para whitelist
from home.models import WhitelistCountryPreference  # noqa
from home.countries import ALL_COUNTRIES  # noqa


# -----------------------------------
# Utilidades para extraer tokens
# -----------------------------------
def collect_tokens(obj: Any) -> List[str]:
    """Recorre recursivamente el JSON y acumula todos los posibles tokens en orden."""
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
    Llama al webhook (n8n) y devuelve el token de Site24x7.
    Toma siempre el 3er token si hay 3 o más; si no, el último.
    """
    if not SITE24X7_WEBHOOK_URL:
        raise RuntimeError("SITE24X7_WEBHOOK_URL no está configurada.")
    if not SITE24X7_WEBHOOK_SECRET:
        raise RuntimeError("SITE24X7_WEBHOOK_SECRET no está configurada.")

    headers = {SITE24X7_WEBHOOK_HEADER_NAME: SITE24X7_WEBHOOK_SECRET}
    req = urllib.request.Request(url=SITE24X7_WEBHOOK_URL, method="GET", headers=headers)
    ctx = ssl.create_default_context() if SITE24X7_VERIFY_SSL else ssl._create_unverified_context()

    try:
        with urllib.request.urlopen(req, timeout=20, context=ctx) as resp:
            status = resp.getcode()
            body = resp.read()
    except Exception as e:
        raise RuntimeError(f"Error al llamar la API del webhook: {e}")

    text = body.decode("utf-8", errors="replace").strip()

    if status // 100 != 2:
        raise RuntimeError(f"Webhook respondió HTTP {status}")

    # Igual que el script: intentar JSON y extraer tokens por claves
    try:
        data = json.loads(text)
        tokens = collect_tokens(data)

        if not tokens:
            raise RuntimeError("No se encontraron tokens en el JSON del webhook.")

        # 3er token = Site24x7, si existe; si no, el último
        chosen = tokens[2] if len(tokens) >= 3 else tokens[-1]

        try:
            TOKEN_FILE.write_text(chosen, encoding="utf-8")
        except Exception:
            pass

        return chosen

    except json.JSONDecodeError:
        # No es JSON, usar cuerpo directo como token
        if not text:
            raise RuntimeError("Respuesta vacía del webhook de token (no es JSON).")
        try:
            TOKEN_FILE.write_text(text, encoding="utf-8")
        except Exception:
            pass
        return text


# -----------------------------------
# Helpers para tiempo “Hace X minutos”
# -----------------------------------
def _parse_site24x7_timestamp(value: Any):
    """Convierte last_polled_time (epoch ms o ISO) a datetime en UTC."""
    if not value:
        return None

    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(value / 1000.0, tz=timezone.utc)
        except Exception:
            return None

    if isinstance(value, str):
        s = value.strip()
        if not s:
            return None

        if s.isdigit():
            try:
                return datetime.fromtimestamp(int(s) / 1000.0, tz=timezone.utc)
            except Exception:
                pass

        try:
            iso = s.replace("Z", "+00:00")
            dt = datetime.fromisoformat(iso)
            if timezone.is_naive(dt):
                dt = timezone.make_aware(dt, timezone.utc)
            return dt
        except Exception:
            pass

    return None


def _humanize_delta(delta):
    """Devuelve un texto tipo 'Hace X minutos' a partir de un timedelta."""
    seconds = int(delta.total_seconds())
    if seconds < 60:
        return "Hace menos de 1 minuto"

    minutes = seconds // 60
    if minutes < 60:
        return f"Hace {minutes} minuto{'s' if minutes != 1 else ''}"

    hours = minutes // 60
    if hours < 24:
        return f"Hace {hours} hora{'s' if hours != 1 else ''}"

    days = hours // 24
    return f"Hace {days} día{'s' if days != 1 else ''}"


def format_last_polled(raw_value: Any) -> str:
    """Formatea last_polled_time en texto relativo para la tabla."""
    dt = _parse_site24x7_timestamp(raw_value)
    if not dt:
        return "—"

    now = timezone.now()
    if dt > now:
        return "Hace instantes"

    delta = now - dt
    return _humanize_delta(delta)


# -----------------------------------
# Llamado a Site24x7 – Customer Wise Monitor Status
# -----------------------------------
def fetch_customer_status(access_token: str, zaaid: str) -> Dict[str, Any]:
    """
    Llama a /msp/customers/monitors/status y devuelve el bloque
    de datos del cliente que corresponde al zaaid.
    """
    headers = {
        "Accept": "application/json; version=2.0",
        "Authorization": f"Zoho-oauthtoken {access_token}",
    }

    url = f"{SITE24X7_API_BASE_URL}{CURRENT_STATUS_PATH}"
    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    customers = data.get("data", [])
    for customer in customers:
        if str(customer.get("zaaid")) == str(zaaid):
            return customer

    return {}


def build_counters(monitors: List[Dict[str, Any]]) -> Dict[str, int]:
    """
    Cuenta monitores por estado:
    down, up, trouble, critical, suspended.
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


# -----------------------------------
# Vista principal
# -----------------------------------
@tenant_required
@login_required
def monitor_status(request):
    """
    Vista de estado de monitores Site24x7.
    Usa tenant.site24x7_id como zaaid y token desde webhook.
    """
    tenant = getattr(request, "tenant", None)

    if tenant is None:
        tu = (
            TenantUser.objects
            .filter(user=request.user)
            .select_related("tenant")
            .first()
        )
        tenant = tu.tenant if tu else None

    tenants_list = []
    user_tenant = getattr(request, "tenant", None)
    if user_tenant and getattr(user_tenant, "name", "").lower() == "inntesec":
        tenants_list = Tenant.objects.all().order_by("name")

    if tenant is None:
        selected_paises = []
        try:
            pref = WhitelistCountryPreference.objects.get(user=request.user)
            selected_paises = pref.paises or []
        except WhitelistCountryPreference.DoesNotExist:
            selected_paises = []
        except Exception as e:
            logger.exception("[SITE24X7] Error leyendo preferencias de países: %s", e)
            selected_paises = []

        context = {
            "tenant": None,
            "all_tenants": tenants_list,
            "error": "No se pudo determinar el tenant para este usuario.",
            "customer_name": "",
            "monitors": [],
            "zaaid": "",
            "total_monitors": 0,
            "count_down": 0,
            "count_up": 0,
            "count_trouble": 0,
            "count_critical": 0,
            "count_suspended": 0,
            "whitelist_countries": ALL_COUNTRIES,
            "selected_paises": selected_paises,
        }
        return render(request, "site24x7/monitor_status.html", context)

    zaaid = getattr(tenant, "site24x7_id", "")

    if not zaaid:
        selected_paises = []
        try:
            pref = WhitelistCountryPreference.objects.get(user=request.user)
            selected_paises = pref.paises or []
        except WhitelistCountryPreference.DoesNotExist:
            selected_paises = []
        except Exception as e:
            logger.exception("[SITE24X7] Error leyendo preferencias de países: %s", e)
            selected_paises = []

        context = {
            "tenant": tenant,
            "all_tenants": tenants_list,
            "error": "",
            "customer_name": "",
            "monitors": [],
            "zaaid": "",
            "total_monitors": 0,
            "count_down": 0,
            "count_up": 0,
            "count_trouble": 0,
            "count_critical": 0,
            "count_suspended": 0,
            "whitelist_countries": ALL_COUNTRIES,
            "selected_paises": selected_paises,
        }
        return render(request, "site24x7/monitor_status.html", context)

    try:
        access_token = get_site24x7_token()
        customer = fetch_customer_status(access_token, zaaid)
    except Exception as e:
        selected_paises = []
        try:
            pref = WhitelistCountryPreference.objects.get(user=request.user)
            selected_paises = pref.paises or []
        except WhitelistCountryPreference.DoesNotExist:
            selected_paises = []
        except Exception as e2:
            logger.exception("[SITE24X7] Error leyendo preferencias de países: %s", e2)
            selected_paises = []

        context = {
            "tenant": tenant,
            "all_tenants": tenants_list,
            "error": f"Error al consultar Site24x7: {e}",
            "customer_name": "",
            "monitors": [],
            "zaaid": zaaid or "",
            "total_monitors": 0,
            "count_down": 0,
            "count_up": 0,
            "count_trouble": 0,
            "count_critical": 0,
            "count_suspended": 0,
            "whitelist_countries": ALL_COUNTRIES,
            "selected_paises": selected_paises,
        }
        return render(request, "site24x7/monitor_status.html", context)

    raw_monitors = customer.get("monitors", []) or []

    monitors: List[Dict[str, Any]] = []
    for m in raw_monitors:
        m_copy = dict(m)
        m_copy["last_polled_human"] = format_last_polled(m_copy.get("last_polled_time"))
        monitors.append(m_copy)

    counters = build_counters(monitors)

    selected_paises = []
    try:
        pref = WhitelistCountryPreference.objects.get(user=request.user)
        selected_paises = pref.paises or []
    except WhitelistCountryPreference.DoesNotExist:
        selected_paises = []
    except Exception as e:
        logger.exception("[SITE24X7] Error leyendo preferencias de países: %s", e)
        selected_paises = []

    context = {
        "tenant": tenant,
        "all_tenants": tenants_list,
        "error": "",
        "customer_name": customer.get("customer_name", ""),
        "zaaid": customer.get("zaaid", zaaid),
        "monitors": monitors,
        "total_monitors": len(monitors),
        "count_down": counters["down"],
        "count_up": counters["up"],
        "count_trouble": counters["trouble"],
        "count_critical": counters["critical"],
        "count_suspended": counters["suspended"],
        "whitelist_countries": ALL_COUNTRIES,
        "selected_paises": selected_paises,
    }

    return render(request, "site24x7/monitor_status.html", context)


@tenant_required
@login_required
def dashboard(request):
    """
    Dashboard de Site24x7 embebido en un iframe.
    Usa TenantDashboardEmbed por tenant y muestra selector si el usuario es Inntesec.
    """
    tenant = getattr(request, "tenant", None)

    if tenant is None:
        tenant_id = request.session.get("tenant_id")
        if tenant_id:
            tenant = Tenant.objects.filter(id=tenant_id).first()

    if tenant is None:
        tenant = getattr(request.user, "tenant", None)

    tenants_list = []
    user_tenant = getattr(request.user, "tenant", None)
    if user_tenant and getattr(user_tenant, "name", "").lower() == "inntesec":
        tenants_list = Tenant.objects.all().order_by("name")

    selected_paises = []
    try:
        pref = WhitelistCountryPreference.objects.get(user=request.user)
        selected_paises = pref.paises or []
    except WhitelistCountryPreference.DoesNotExist:
        selected_paises = []
    except Exception as e:
        logger.exception("[SITE24X7] Error leyendo preferencias de países: %s", e)
        selected_paises = []

    if tenant is None:
        context = {
            "tenant": None,
            "all_tenants": tenants_list,
            "iframe_url": None,
            "whitelist_countries": ALL_COUNTRIES,
            "selected_paises": selected_paises,
        }
        return render(request, "site24x7/dashboard.html", context)

    iframe_url = None
    try:
        embed = tenant.dashboard_iframe
        iframe_url = embed.iframe_url
    except TenantDashboardEmbed.DoesNotExist:
        iframe_url = None
    except TenantDashboardEmbed.MultipleObjectsReturned:
        embed = TenantDashboardEmbed.objects.filter(tenant=tenant).first()
        iframe_url = embed.iframe_url if embed else None

    context = {
        "tenant": tenant,
        "all_tenants": tenants_list,
        "iframe_url": iframe_url,
        "whitelist_countries": ALL_COUNTRIES,
        "selected_paises": selected_paises,
    }
    return render(request, "site24x7/dashboard.html", context)
