# mysite/siem/views.py
from __future__ import annotations

from datetime import datetime, date
import json
import re
import logging

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.core.paginator import Paginator
from django.shortcuts import render
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseForbidden, HttpResponseServerError
from django.utils.html import escape

import re

from tenants.decorators import tenant_required, service_required
from tenants.models import Tenant, TenantDashboardEmbed
from .log360_service import obtener_alertas_logs360

# credenciales del portal + preferencias de países
from home.models import TenantCredentials, WhitelistCountryPreference
from home.countries import ALL_COUNTRIES

logger = logging.getLogger(__name__)


# ======================================================
# Helpers comunes
# ======================================================
def _parse_date(s: str | None) -> date | None:
    """Parsea fecha YYYY-MM-DD o devuelve None."""
    if not s:
        return None
    s = str(s).strip()
    if not s:
        return None
    try:
        return datetime.strptime(s[:10], "%Y-%m-%d").date()
    except Exception:
        return None





def _tenants_list_for_user(user):
    """
    Selector de tenants SOLO para Inntesec.
    Retorna queryset/list ordenado por name.
    """
    user_tenant = getattr(user, "tenant", None)
    if user_tenant and (user_tenant.name or "").strip().lower() == "inntesec":
        return Tenant.objects.all().order_by("name")
    return []


def _active_cred_for_tenant(tenant):
    """
    Credencial activa del tenant (si existe).
    """
    try:
        if tenant:
            return TenantCredentials.get_active_for_tenant(int(getattr(tenant, "id", 0)))
    except Exception:
        logger.exception("[SIEM] Error obteniendo credenciales del tenant.")
    return None


def _selected_paises_for_tenant(tenant, fallback_user=None) -> list[str]:
    """
    Preferencias de países whitelist (POR TENANT).
    Si tenant es None, intenta con fallback_user.tenant si se entrega.
    """
    try:
        effective = tenant
        if effective is None and fallback_user is not None:
            effective = getattr(fallback_user, "tenant", None)

        if not effective:
            return []

        pref = WhitelistCountryPreference.objects.filter(tenant=effective).first()
        return (pref.paises or []) if pref else []
    except Exception:
        logger.exception("[SIEM] Error leyendo preferencias de países (tenant).")
        return []


def _get_embed_url(tenant, field_name: str) -> str | None:
    """
    Lee una URL desde public.tenants_tenantdashboardembed.<field_name> para el tenant.
    Retorna None si no existe el embed o el campo está vacío.
    """
    if not tenant:
        return None
    embed = TenantDashboardEmbed.objects.filter(tenant=tenant).first()
    if not embed:
        return None
    return (getattr(embed, field_name, None) or "").strip() or None


def _enhance_alert_for_template(alert: dict) -> dict:
    """
    Agrega datos derivados para el template:
      - __device_name__
      - __device_id__
      - __device_label__
      - __raw_json__
    """
    enhanced = dict(alert)

    msg = alert.get("Message") or ""
    devname = ""
    devid = ""

    if isinstance(msg, str) and msg:
        # Ejemplo: devname="FortiGate-60E" devid="FGT60ETK18099LU2"
        m_name = re.search(r'devname="([^"]+)"', msg)
        if m_name:
            devname = m_name.group(1)

        m_id = re.search(r'devid="([^"]+)"', msg)
        if m_id:
            devid = m_id.group(1)

    label_parts: list[str] = []
    if devname:
        label_parts.append(devname)
    if devid:
        if devname:
            label_parts.append(f"({devid})")
        else:
            label_parts.append(devid)

    device_label = " ".join(label_parts) if label_parts else ""

    enhanced["__device_name__"] = devname
    enhanced["__device_id__"] = devid
    enhanced["__device_label__"] = device_label

    try:
        raw_json = json.dumps(alert, ensure_ascii=False, indent=2)
    except TypeError:
        raw_json = json.dumps(str(alert), ensure_ascii=False, indent=2)

    enhanced["__raw_json__"] = raw_json

    return enhanced


# ======================================================
# Views existentes
# ======================================================
@login_required
@tenant_required
@service_required("logs360siem_id")
def alerts_logs360_view(request):
    """
    Lista de alertas Logs360.
    - Usa logs360siem_id del tenant.
    - Llama al service que fuerza rango últimos 30 días.
    - En errores de token / HTTP muestra mensaje genérico.
    """
    tenant = getattr(request, "tenant", None)

    raw_siem_id = getattr(tenant, "logs360siem_id", "") if tenant else ""
    siem_id = str(raw_siem_id or "").strip()
    service_enabled = bool(siem_id) and siem_id not in ("0", "null", "NULL", "None")

    tenants_list = _tenants_list_for_user(request.user)

    # credenciales activas del tenant
    cred = _active_cred_for_tenant(tenant)

    # Sanitizar q: evita payload gigante / logs enormes / abuso suave
    q_raw = request.GET.get("q") or ""
    q = str(q_raw).strip()
    if len(q) > 200:
        q = q[:200]

    # el service fuerza rango de fechas; aquí no usamos los inputs del form
    from_date = None
    to_date = None

    alerts_raw: list[dict] = []
    error_internal = None   # mensaje técnico interno
    error_public = None     # mensaje genérico para UI
    start_time = ""
    end_time = ""
    siem_account_id = ""

    if service_enabled:
        try:
            alerts_raw, error_internal, start_time, end_time, siem_account_id = obtener_alertas_logs360(
                query=q,
                account_id=siem_id,
                from_date=from_date,
                to_date=to_date,
            )
        except Exception:
            logger.exception("[LOGS360] Excepción consultando Logs360.")
            error_internal = "exception"

        # cualquier error se traduce a un mensaje genérico (NO filtramos detalles)
        if error_internal:
            logger.error(
                "[LOGS360] Error consultando Logs360 (detalles internos ocultos). tenant_id=%s user_id=%s",
                getattr(tenant, "id", None),
                getattr(request.user, "id", None),
            )
            error_public = (
                "No fue posible recuperar las alertas de Logs360 SIEM en este momento. "
                "Por favor, contacte con un administrador."
            )

    # enriquecer alertas para el template
    alerts: list[dict] = [_enhance_alert_for_template(a) for a in alerts_raw]

    # fechas para mostrar en los inputs del template
    def _extract_date_str(iso_dt: str) -> str:
        if not iso_dt:
            return ""
        return str(iso_dt)[:10]

    from_date_str = _extract_date_str(start_time)
    to_date_str = _extract_date_str(end_time)

    paginator = Paginator(alerts, 50)
    page_obj = paginator.get_page(request.GET.get("page") or 1)

    # Países whitelist (POR TENANT)
    selected_paises = _selected_paises_for_tenant(tenant, fallback_user=request.user)

    # Solo mostrar error_internal si staff o DEBUG
    can_show_internal = bool(getattr(request.user, "is_staff", False)) or bool(getattr(settings, "DEBUG", False))
    error_internal_safe = error_internal if can_show_internal else None

    context = {
        "tenant": tenant,
        "all_tenants": tenants_list,

        "service_enabled": service_enabled,
        "has_siem": service_enabled,  # nombre antiguo del template

        "alerts": alerts,
        "alerts_total": len(alerts),
        "total": len(alerts),
        "page_obj": page_obj,

        # error genérico para UI (None si todo ok)
        "error": error_public,
        # error técnico SOLO si admin/staff o DEBUG
        "error_internal": error_internal_safe,

        "q": q,
        "from_date_str": from_date_str,
        "to_date_str": to_date_str,
        "start_time": start_time,
        "end_time": end_time,
        "logs360_account_id": siem_account_id,
        "siem_account_id": siem_account_id,

        "cred": cred,
        "whitelist_countries": ALL_COUNTRIES,
        "selected_paises": selected_paises,
    }
    return render(request, "siem/alerts_list.html", context)


# ======================================================
# Nuevas vistas: 4 páginas iframe (desde tenants_tenantdashboardembed)
# ======================================================
@login_required
@tenant_required
@service_required("logs360siem_id")
def threat_analytics(request):
    tenant = getattr(request, "tenant", None)
    tenants_list = _tenants_list_for_user(request.user)

    context = {
        "tenant": tenant,
        "all_tenants": tenants_list,
        "iframe_url": _get_embed_url(tenant, "threat_analytics"),
        "page_title": "Threat Analytics",
        "active_page": "threat_analytics",
        "cred": _active_cred_for_tenant(tenant),
        "whitelist_countries": ALL_COUNTRIES,
        "selected_paises": _selected_paises_for_tenant(tenant, fallback_user=request.user),
    }
    return render(request, "siem/threat_analytics.html", context)


@login_required
@tenant_required
@service_required("logs360siem_id")
def microsoft365(request):
    tenant = getattr(request, "tenant", None)
    tenants_list = _tenants_list_for_user(request.user)

    context = {
        "tenant": tenant,
        "all_tenants": tenants_list,
        "iframe_url": _get_embed_url(tenant, "microsoft365"),
        "page_title": "Microsoft 365",
        "active_page": "microsoft365",
        "cred": _active_cred_for_tenant(tenant),
        "whitelist_countries": ALL_COUNTRIES,
        "selected_paises": _selected_paises_for_tenant(tenant, fallback_user=request.user),
    }
    return render(request, "siem/microsoft365.html", context)


@login_required
@tenant_required
@service_required("logs360siem_id")
def networks(request):
    tenant = getattr(request, "tenant", None)
    tenants_list = _tenants_list_for_user(request.user)

    context = {
        "tenant": tenant,
        "all_tenants": tenants_list,
        "iframe_url": _get_embed_url(tenant, "networks"),
        "page_title": "Networks",
        "active_page": "networks",
        "cred": _active_cred_for_tenant(tenant),
        "whitelist_countries": ALL_COUNTRIES,
        "selected_paises": _selected_paises_for_tenant(tenant, fallback_user=request.user),
    }
    return render(request, "siem/networks.html", context)


@login_required
@tenant_required
@service_required("logs360siem_id")
def eventos_diarios(request):
    tenant = getattr(request, "tenant", None)
    tenants_list = _tenants_list_for_user(request.user)

    context = {
        "tenant": tenant,
        "all_tenants": tenants_list,
        "iframe_url": _get_embed_url(tenant, "eventos_diarios"),
        "page_title": "Eventos diarios",
        "active_page": "eventos_diarios",
        "cred": _active_cred_for_tenant(tenant),
        "whitelist_countries": ALL_COUNTRIES,
        "selected_paises": _selected_paises_for_tenant(tenant, fallback_user=request.user),
    }
    return render(request, "siem/eventos_diarios.html", context)


