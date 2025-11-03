from __future__ import annotations
import logging
from typing import Iterable

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import F, Value, TextField
from django.db.models.functions import Lower, Replace, Trim, Cast
from django.shortcuts import render, redirect

from tenants.decorators import tenant_required
from tenants.models import Tenant
from .models import IaSoar

logger = logging.getLogger(__name__)

# ============================================================
# 🧩 Helpers de normalización
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

# ============================================================
# 🧩 Dashboard SOAR (principal)
# ============================================================
@login_required
@tenant_required
def dashboard_soar(request):
    """
    Renderiza el panel SOAR filtrado por tenant.
    Si el usuario pertenece a Inntesec, muestra el selector de tenants.
    """
    tenant = getattr(request, "tenant", None)
    norm_tid = _normalize_tenant_aotag(tenant) if tenant else ""

    logger.info("[SOAR] Entrando a dashboard_soar | tenant=%s | alarms_one_id(raw)=%s | alarms_one_id(norm)=%s",
                getattr(tenant, "name", None),
                getattr(tenant, "alarms_one_id", None),
                norm_tid)

    rows: Iterable[dict] = []
    try:
        qs = IaSoar.objects.all()
        if norm_tid:
            qs = _annotate_norm_aotag(qs).filter(norm_aotag=norm_tid)
        else:
            logger.warning("[SOAR] request sin tenant o sin alarms_one_id -> 0 filas")
            qs = qs.none()

        rows = list(qs.values(
            "date", "time",
            "device", "service", "proto",
            "srccountry",
            "severity",
            "security_action",
            "action",
        )[:20000])

    except Exception as e:
        logger.exception("[SOAR] Error consultando IaSoar: %s", e)
        rows = []

    # --- Selector de tenants solo visible para Inntesec ---
    tenants_list = []
    user_tenant = getattr(request.user, "tenant", None)
    if user_tenant and user_tenant.name.lower() == "inntesec":
        tenants_list = Tenant.objects.all().order_by("name")

    ctx = {
        "tenant": tenant,
        "events": rows,
        "all_tenants": tenants_list,
        "request": request,
    }
    return render(request, "soar_dashboard/dashboardsoar.html", ctx)

# ============================================================
# 🧩 Cambio de Tenant universal (desde cualquier dashboard)
# ============================================================
@login_required
def switch_tenant(request, tenant_id):
    """
    Permite a usuarios de Inntesec cambiar de tenant desde cualquier dashboard.
    Redirige automáticamente al mismo módulo (SOAR, Realtime, Histórico).
    """
    user_tenant = getattr(request.user, "tenant", None)
    if not user_tenant or user_tenant.name.lower() != "inntesec":
        messages.error(request, "No tienes permiso para cambiar de empresa.")
        return redirect("dashboard")

    tenant = Tenant.objects.filter(id=tenant_id).first()
    if not tenant:
        messages.error(request, "El tenant seleccionado no existe.")
        return redirect("dashboard")

    # --- Guardar tenant seleccionado en la sesión ---
    request.session["tenant_id"] = tenant.id
    request.session["tenant_name"] = tenant.name
    logger.info("[SwitchTenant] %s cambió a tenant %s", request.user.username, tenant.name)

    # --- Detectar el origen real ---
    next_url = (
        request.POST.get("next")
        or request.GET.get("next")
        or request.META.get("HTTP_REFERER", "")
    ).lower()

    logger.debug("[SwitchTenant] next_url detectado: %s", next_url)

    # --- Reglas inteligentes de redirección ---
    # Orden de prioridad: SOAR → Realtime → Alarmas → Dashboard principal
    if "dashboard-soar" in next_url:
        logger.debug("[SwitchTenant] Redirigiendo al dashboard SOAR")
        return redirect("soar_dashboard:dashboard")

    if "dashboard/realtime" in next_url or "realtime" in next_url:
        logger.debug("[SwitchTenant] Redirigiendo al dashboard Tiempo Real")
        return redirect("dashboard_realtime")

    if "dashboard/alarmsone" in next_url or "alarmsone" in next_url:
        logger.debug("[SwitchTenant] Redirigiendo al dashboard Histórico de Alarmas")
        return redirect("dashboard_alarmsone")

    # --- Si no detecta origen, revisa el referer de nuevo ---
    referer = (request.META.get("HTTP_REFERER") or "").lower()
    logger.debug("[SwitchTenant] Referer=%s", referer)

    if "dashboard-soar" in referer:
        return redirect("soar_dashboard:dashboard")
    if "dashboard/realtime" in referer or "realtime" in referer:
        return redirect("dashboard_realtime")
    if "dashboard/alarmsone" in referer or "alarmsone" in referer:
        return redirect("dashboard_alarmsone")

    # --- Fallback final ---
    logger.debug("[SwitchTenant] No se detectó origen, redirigiendo al dashboard principal")
    return redirect("dashboard")
