# site24x7/views.py
import json
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
from django.shortcuts import render

# =========================
# Configuración TOKEN WEBHOOK
# =========================
TOKEN_URL = "https://iaproductivo.inntesec.cl/webhook/3c850e31-e699-4fa6-9fed-513d4ccd281b"
SECRET = "@L^E4$h!f^r1VmwD#c1B#C8XzM#B4pON"
HEADER_NAME = "passkey"
VERIFY_SSL = True

TOKEN_FILE = Path(__file__).resolve().parent / "token.txt"

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

# =========================
# Configuración Site24x7
# =========================
SITE24X7_BASE_URL = "https://www.site24x7.com/api"
CURRENT_STATUS_PATH = "/msp/customers/monitors/status"  # Customer Wise Monitor Status


# -----------------------------------
# Utilidades para extraer tokens
# -----------------------------------
def collect_tokens(obj: Any) -> List[str]:
    """Recorre recursivamente y devuelve todos los tokens encontrados, en orden."""
    found: List[str] = []
    if isinstance(obj, dict):
        lowered = {k.lower() for k in CANDIDATE_KEYS}
        for k, v in obj.items():
            if isinstance(k, str):
                key_norm = k.strip().lower()
                if key_norm in lowered and isinstance(v, str) and v.strip():
                    found.append(v.strip())
            # seguir recorriendo
            found.extend(collect_tokens(v))
    elif isinstance(obj, list):
        for item in obj:
            found.extend(collect_tokens(item))
    return found


def get_site24x7_token() -> str:
    """
    Llama al webhook, parsea la respuesta y toma SIEMPRE el 3er token
    (Site24x7). Si por alguna razón no hubiera 3, toma el último.
    """
    headers = {HEADER_NAME: SECRET}
    req = urllib.request.Request(url=TOKEN_URL, method="GET", headers=headers)
    ctx = ssl.create_default_context() if VERIFY_SSL else ssl._create_unverified_context()

    try:
        with urllib.request.urlopen(req, timeout=20, context=ctx) as resp:
            status = resp.getcode()
            body = resp.read()
    except Exception as e:
        raise RuntimeError(f"Error al llamar la API del webhook: {e}")

    text = body.decode("utf-8", errors="replace").strip()

    if status // 100 != 2:
        raise RuntimeError(f"Webhook respondió HTTP {status}")

    # Intentar JSON, igual que tu script
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
            pass

        return chosen

    except json.JSONDecodeError:
        # Si no es JSON, tratamos la respuesta entera como token
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
    """
    Intenta parsear last_polled_time de Site24x7.
    Puede venir como:
    - epoch en milisegundos (int/str)
    - ISO string
    """
    if not value:
        return None

    # Epoch ms como int/float
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(value / 1000.0, tz=timezone.utc)
        except Exception:
            return None

    # Como string
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return None

        # Epoch ms como string
        if s.isdigit():
            try:
                return datetime.fromtimestamp(int(s) / 1000.0, tz=timezone.utc)
            except Exception:
                pass

        # ISO-like
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
    dt = _parse_site24x7_timestamp(raw_value)
    if not dt:
        return "—"

    now = timezone.now()
    # Por si llega con hora futura por desajuste de hora
    if dt > now:
        return "Hace instantes"

    delta = now - dt
    return _humanize_delta(delta)


# -----------------------------------
# Llamado a Site24x7 – Customer Wise Monitor Status
# -----------------------------------
def fetch_customer_status(access_token: str, zaaid: str) -> Dict[str, Any]:
    """
    Llama a /msp/customers/monitors/status y devuelve el bloque del cliente
    que corresponde al zaaid indicado.
    """
    headers = {
        "Accept": "application/json; version=2.0",
        # 👇 AHORA usamos el token que viene del webhook
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


def build_counters(monitors: List[Dict[str, Any]]) -> Dict[str, int]:
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


# -----------------------------------
# Vista principal
# -----------------------------------
@tenant_required
@login_required
def monitor_status(request):
    """
    Vista de estado de monitores Site24x7
    - Usa Tenant.site24x7_id como zaaid
    - Token OAuth obtenido desde webhook (3er token)
    - Estilo similar a SOAR Incidentes
    """
    # --- Tenant activo (middleware) ---
    tenant = getattr(request, "tenant", None)

    if tenant is None:
        tu = (
            TenantUser.objects
            .filter(user=request.user)
            .select_related("tenant")
            .first()
        )
        tenant = tu.tenant if tu else None

    # === Selector solo visible si el usuario pertenece a Inntesec ===
    tenants_list = []
    user_tenant = getattr(request.user, "tenant", None)
    if user_tenant and getattr(user_tenant, "name", "").lower() == "inntesec":
        tenants_list = Tenant.objects.all().order_by("name")

    # Si no hay tenant, pantalla vacía
    if tenant is None:
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
        }
        return render(request, "site24x7/monitor_status.html", context)

    zaaid = getattr(tenant, "site24x7_id", "")

    # Si el tenant no tiene site24x7_id -> que lo maneje el template como “servicio no disponible”
    if not zaaid:
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
        }
        return render(request, "site24x7/monitor_status.html", context)

    # --- Llamar Site24x7 ---
    try:
        access_token = get_site24x7_token()
        customer = fetch_customer_status(access_token, zaaid)
    except Exception as e:
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
        }
        return render(request, "site24x7/monitor_status.html", context)

    raw_monitors = customer.get("monitors", []) or []

    # Enriquecer monitores con last_polled_human
    monitors: List[Dict[str, Any]] = []
    for m in raw_monitors:
        m_copy = dict(m)
        m_copy["last_polled_human"] = format_last_polled(m_copy.get("last_polled_time"))
        monitors.append(m_copy)

    counters = build_counters(monitors)

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
    }

    return render(request, "site24x7/monitor_status.html", context)

@tenant_required
@login_required
def dashboard(request):
    """
    Vista del dashboard de Site24x7 embebido en un iframe.

    - Usa el tenant ACTIVO (request.tenant o session['tenant_id']).
    - Si el usuario pertenece a Inntesec, muestra selector de tenants (all_tenants),
      igual que monitor_status.
    - Busca la URL en TenantDashboardEmbed (uno por tenant).
    """

    # 1) Resolver tenant activo
    tenant = getattr(request, "tenant", None)

    # Fallback: tomarlo desde la sesión si el middleware no lo puso
    if tenant is None:
        tenant_id = request.session.get("tenant_id")
        if tenant_id:
            tenant = Tenant.objects.filter(id=tenant_id).first()

    # Último fallback: tenant base del usuario
    if tenant is None:
        tenant = getattr(request.user, "tenant", None)

    # 2) Lista de tenants para el selector (solo si el usuario es Inntesec)
    tenants_list = []
    user_tenant = getattr(request.user, "tenant", None)
    if user_tenant and getattr(user_tenant, "name", "").lower() == "inntesec":
        tenants_list = Tenant.objects.all().order_by("name")

    # 3) Sin tenant → mostramos mensaje genérico
    if tenant is None:
        context = {
            "tenant": None,
            "all_tenants": tenants_list,
            "iframe_url": None,
        }
        return render(request, "site24x7/dashboard.html", context)

    # 4) Buscar URL del iframe para este tenant
    iframe_url = None
    try:
        # usando la relación OneToOne
        embed = tenant.dashboard_iframe
        iframe_url = embed.iframe_url
    except TenantDashboardEmbed.DoesNotExist:
        iframe_url = None
    except TenantDashboardEmbed.MultipleObjectsReturned:
        # por si en algún momento se llega a duplicar: tomamos el primero
        embed = TenantDashboardEmbed.objects.filter(tenant=tenant).first()
        iframe_url = embed.iframe_url if embed else None

    context = {
        "tenant": tenant,
        "all_tenants": tenants_list,
        "iframe_url": iframe_url,
    }
    return render(request, "site24x7/dashboard.html", context)