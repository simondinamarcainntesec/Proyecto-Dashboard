from __future__ import annotations

from datetime import datetime, date
import json
import re
import logging

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import render
from tenants.decorators import tenant_required
from tenants.models import Tenant

from .log360_service import obtener_alertas_logs360

# <<< NUEVO: credenciales del portal + preferencias de países
from home.models import TenantCredentials, WhitelistCountryPreference  # noqa
from home.countries import ALL_COUNTRIES

logger = logging.getLogger(__name__)


def _parse_date(s: str | None) -> date | None:
    if not s:
        return None
    s = str(s).strip()
    if not s:
        return None
    try:
        return datetime.strptime(s[:10], "%Y-%m-%d").date()
    except Exception:
        return None


def _enhance_alert_for_template(alert: dict) -> dict:
    """
    A partir del dict original de Logs360, agrega:
      - __device_name__  (devname extraído de Message)
      - __device_id__    (devid extraído de Message)
      - __device_label__ (devname + devid formateado)
      - __raw_json__     (JSON pretty con todos los campos)
    para uso exclusivo en el template.
    """
    enhanced = dict(alert)

    msg = alert.get("Message") or ""
    devname = ""
    devid = ""

    if isinstance(msg, str) and msg:
        # Ejemplo dentro de Message:
        # devname="FortiGate-60E" devid="FGT60ETK18099LU2"
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
        # fallback muy defensivo
        raw_json = json.dumps(str(alert), ensure_ascii=False, indent=2)

    enhanced["__raw_json__"] = raw_json

    return enhanced


@login_required
@tenant_required
def alerts_logs360_view(request):
    tenant = getattr(request, "tenant", None)

    raw_siem_id = getattr(tenant, "logs360siem_id", "") if tenant else ""
    siem_id = str(raw_siem_id or "").strip()
    service_enabled = bool(siem_id) and siem_id not in ("0", "null", "NULL", "None")

    # selector de tenants solo para Inntesec
    tenants_list = []
    user_tenant = getattr(request.user, "tenant", None)
    if user_tenant and user_tenant.name.lower() == "inntesec":
        tenants_list = Tenant.objects.all().order_by("name")

    # <<< NUEVO: obtener credenciales activas del tenant
    cred = None
    try:
        if tenant:
            cred = TenantCredentials.get_active_for_tenant(
                int(getattr(tenant, "id", 0))
            )
    except Exception as e:
        logger.exception("[LOGS360] Error obteniendo credenciales del tenant: %s", e)
    # >>> FIN NUEVO

    q = (request.GET.get("q") or "").strip()

    # ⚠️ IMPORTANTE:
    # Ya NO usamos los filtros de fecha del HTML para la consulta.
    # El service fuerza el rango (últimos 30 días).
    from_date = None
    to_date = None

    alerts_raw: list[dict] = []
    error = None
    start_time = ""
    end_time = ""
    siem_account_id = ""

    if service_enabled:
        alerts_raw, error, start_time, end_time, siem_account_id = obtener_alertas_logs360(
            query=q,
            account_id=siem_id,
            from_date=from_date,
            to_date=to_date,
        )

    # Enriquecer cada alerta con devname/devid + JSON completo para el modal
    alerts: list[dict] = [_enhance_alert_for_template(a) for a in alerts_raw]

    # Para que los <input type="date"> muestren el rango real consultado:
    def _extract_date_str(iso_dt: str) -> str:
        if not iso_dt:
            return ""
        return str(iso_dt)[:10]

    from_date_str = _extract_date_str(start_time)
    to_date_str = _extract_date_str(end_time)

    paginator = Paginator(alerts, 50)
    page_obj = paginator.get_page(request.GET.get("page") or 1)

    # ==============================
    # Países para el modal de whitelist
    # ==============================
    selected_paises = []
    try:
        pref = WhitelistCountryPreference.objects.get(user=request.user)
        selected_paises = pref.paises or []
    except WhitelistCountryPreference.DoesNotExist:
        selected_paises = []
    except Exception as e:
        logger.exception("[LOGS360] Error leyendo preferencias de países: %s", e)
        selected_paises = []

    context = {
        "tenant": tenant,
        "all_tenants": tenants_list,

        "service_enabled": service_enabled,
        "has_siem": service_enabled,  # por si el template usa el nombre antiguo

        "alerts": alerts,
        "alerts_total": len(alerts),
        "total": len(alerts),  # idem, por compatibilidad
        "page_obj": page_obj,
        "error": error,
        "q": q,

        "from_date_str": from_date_str,
        "to_date_str": to_date_str,

        "start_time": start_time,
        "end_time": end_time,

        "logs360_account_id": siem_account_id,
        "siem_account_id": siem_account_id,  # compatibilidad con el template

        # <<< NUEVO: credenciales para el modal parcial
        "cred": cred,
        # >>> FIN NUEVO

        # <<< NUEVO: datos para el modal de países (misma API que en otros módulos)
        "whitelist_countries": ALL_COUNTRIES,
        "selected_paises": selected_paises,
        # >>> FIN NUEVO
    }
    return render(request, "siem/alerts_list.html", context)
