from __future__ import annotations
import logging
from typing import Iterable, Tuple, Optional
from datetime import datetime, timedelta

import pytz
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import F, Value, TextField
from django.db.models.functions import Lower, Replace, Trim, Cast
from django.shortcuts import render, redirect
from django.utils.timezone import make_aware, is_aware

from tenants.decorators import tenant_required
from tenants.models import Tenant
from .models import IaSoar

# Credenciales de blacklist/portal
from home.models import TenantCredentials, WhitelistCountryPreference
from home.countries import ALL_COUNTRIES

logger = logging.getLogger(__name__)
CL_TZ = pytz.timezone("America/Santiago")

# ============================================================
# Helpers de normalización
# ============================================================
def _normalize_string_local(s: str) -> str:
    if not s:
        return ""
    out = str(s).strip()
    for ch in ['{', '}', '[', ']', '"', "'", " "]:
        out = out.replace(ch, "")
    return out.lower()


def _normalize_tenant_aotag(tenant) -> str:
    raw = getattr(tenant, "alarms_one_id", "") or ""
    return _normalize_string_local(raw)


def _annotate_norm_aotag(qs):
    cleaned = Cast(F("aotag"), TextField())
    for ch in ['{', '}', '[', ']', '"', "'", " "]:
        cleaned = Replace(cleaned, Value(ch), Value(""), output_field=TextField())
    cleaned = Trim(cleaned, output_field=TextField())
    cleaned = Lower(cleaned, output_field=TextField())
    return qs.annotate(norm_aotag=cleaned)


# ============ Fechas ============
def _parse_iso_dt_local(s: str) -> Optional[datetime]:
    if not s:
        return None
    s = s.strip().replace(" ", "T")
    try:
        dt = datetime.fromisoformat(s + ("T00:00:00" if "T" not in s else ""))
    except ValueError:
        return None
    if not is_aware(dt):
        dt = make_aware(dt, CL_TZ)
    else:
        dt = dt.astimezone(CL_TZ)
    return dt


def _default_range_now_30d() -> Tuple[datetime, datetime]:
    now = datetime.now(CL_TZ)
    start = (now - timedelta(days=30)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    end = now
    return start, end


def _normalize_range(
    from_qs: Optional[str], to_qs: Optional[str]
) -> Tuple[datetime, datetime, str, str]:
    if not from_qs and not to_qs:
        f, t = _default_range_now_30d()
    else:
        f = _parse_iso_dt_local(from_qs) or _default_range_now_30d()[0]
        t = _parse_iso_dt_local(to_qs) or _default_range_now_30d()[1]
    f = f.replace(hour=0, minute=0, second=0, microsecond=0)
    t = t.replace(hour=23, minute=59, second=59, microsecond=0)
    return f, t, f.strftime("%Y-%m-%d"), t.strftime("%Y-%m-%d")


# ============================================================
# Dashboard SOAR
# ============================================================
@login_required
@tenant_required
def dashboard_soar(request):
    tenant = getattr(request, "tenant", None)
    norm_tid = _normalize_tenant_aotag(tenant) if tenant else ""

    q_from = request.GET.get("from")
    q_to = request.GET.get("to")
    f_dt, t_dt, from_date_str, to_date_str = _normalize_range(q_from, q_to)

    logger.info(
        "[SOAR] dashboard_soar | tenant=%s | from=%s to=%s",
        getattr(tenant, "name", None),
        f_dt.isoformat(),
        t_dt.isoformat(),
    )

    rows: Iterable[dict] = []
    try:
        qs = IaSoar.objects.all()
        if norm_tid:
            qs = _annotate_norm_aotag(qs).filter(norm_aotag=norm_tid)
        else:
            qs = qs.none()

        has_timestamp = hasattr(IaSoar, "timestamp")
        if has_timestamp:
            qs = qs.filter(timestamp__gte=f_dt, timestamp__lte=t_dt)
        else:
            qs = qs.filter(date__gte=f_dt.date(), date__lte=t_dt.date())

        qs = qs.order_by("-date")[:20000]

        # Incluir alarm_id
        rows = list(
            qs.values(
                "alarm_id",
                "date",
                "time",
                "device",
                "service",
                "proto",
                "srccountry",
                "srcip",
                "dstip",
                "aotag",
                "severity",
                "security_action",
                "action",
                "Application",
            )
        )
    except Exception as e:
        logger.exception("[SOAR] Error consultando IaSoar: %s", e)
        rows = []

    # Credenciales activas del tenant
    cred = None
    try:
        if tenant:
            cred = TenantCredentials.get_active_for_tenant(int(getattr(tenant, "id", 0)))
    except Exception as e:
        logger.exception("[SOAR] Error obteniendo credenciales del tenant: %s", e)

    # Selector de tenants para Inntesec
    tenants_list = []
    user_tenant = getattr(request.user, "tenant", None)
    if user_tenant and user_tenant.name.lower() == "inntesec":
        tenants_list = Tenant.objects.all().order_by("name")

    # ==============================
    # Países para el modal de whitelist (POR TENANT, NO POR USER)
    # ==============================
    selected_paises: list[str] = []
    try:
        effective_tenant_for_pref = tenant or getattr(request.user, "tenant", None)
        if effective_tenant_for_pref:
            pref = WhitelistCountryPreference.objects.filter(
                tenant=effective_tenant_for_pref
            ).first()
            selected_paises = (pref.paises or []) if pref else []
        else:
            selected_paises = []
    except Exception as e:
        logger.exception("[SOAR] Error leyendo preferencias de países (tenant): %s", e)
        selected_paises = []

    ctx = {
        "tenant": tenant,
        "events": rows,
        "all_tenants": tenants_list,
        "from_date_str": from_date_str,
        "to_date_str": to_date_str,
        "request": request,
        "cred": cred,
        # Países para el modal de whitelist
        "whitelist_countries": ALL_COUNTRIES,
        "selected_paises": selected_paises,
    }
    return render(request, "soar_dashboard/dashboardsoar.html", ctx)
