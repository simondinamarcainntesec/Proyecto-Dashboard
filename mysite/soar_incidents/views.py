# soar_incidents/views.py
from __future__ import annotations
from datetime import datetime, timedelta
import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q, F, Value, TextField
from django.db.models.functions import Lower, Replace, Trim, Cast
from django.shortcuts import render, redirect
from django.http import HttpResponseRedirect 
from tenants.decorators import tenant_required
from tenants.models import Tenant
from urllib.parse import urlparse

from .models import IncidenteSOAR

logger = logging.getLogger(__name__)


# ---------- helpers de fechas ----------
def _parse_date(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(str(s).replace(" ", "T")).date()
    except Exception:
        try:
            return datetime.strptime(str(s)[:10], "%Y-%m-%d").date()
        except Exception:
            return None


# ---------- helpers de normalización ----------
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


# ---------- vista principal ----------
@login_required
@tenant_required
def incidents_list(request):
    q = (request.GET.get("q") or "").strip()

    # rango por defecto: últimos 30 días
    today = datetime.now().date()
    default_from = today - timedelta(days=30)
    from_q = _parse_date(request.GET.get("from")) or default_from
    to_q = _parse_date(request.GET.get("to")) or today

    # base queryset
    qs = IncidenteSOAR.objects.all()

    # filtro por TENANT
    tenant = getattr(request, "tenant", None)
    norm_tid = _normalize_tenant_aotag(tenant) if tenant else ""
    if norm_tid:
        qs = _annotate_norm_aotag(qs).filter(norm_aotag=norm_tid)
    else:
        qs = qs.none()

    # filtros adicionales
    qs = qs.filter(date__gte=from_q, date__lte=to_q)
    if q:
        qs = qs.filter(
            Q(alarmd_id__icontains=q)
            | Q(aotag__icontains=q)
            | Q(dispositivo__icontains=q)
            | Q(descripcion_incidente__icontains=q)
            | Q(tipo_de_amenaza__icontains=q)
            | Q(nivel_de_severidad__icontains=q)
            | Q(medidas_correctivas__icontains=q)
            | Q(resumen_humano__icontains=q)
            | Q(riego_detectado__icontains=q)
            | Q(analisis_criticidad__icontains=q)
            | Q(application__icontains=q)
        )

    qs = qs.order_by("-date", "-time")

    paginator = Paginator(qs, 25)
    page_obj = paginator.get_page(request.GET.get("page"))

    # === Selector solo visible si el usuario pertenece a Inntesec ===
    tenants_list = []
    user_tenant = getattr(request.user, "tenant", None)
    if user_tenant and user_tenant.name.lower() == "inntesec":
        tenants_list = Tenant.objects.all().order_by("name")

    context = {
        "page_obj": page_obj,
        "q": q,
        "total": paginator.count,
        "from_date_str": from_q.strftime("%Y-%m-%d"),
        "to_date_str": to_q.strftime("%Y-%m-%d"),
        "tenant": tenant,
        "all_tenants": tenants_list,
    }
    return render(request, "soar_incidents/list.html", context)


# ---------- cambio de tenant ----------
@login_required
def switch_tenant(request, tenant_id):
    """
    Permite a usuarios de Inntesec cambiar de tenant desde cualquier dashboard.
    Mantiene al usuario en el mismo módulo (SOAR, Realtime, Alarmas, etc.)
    tras el cambio, y limpia la caché para evitar datos inconsistentes.
    """
    from tenants.models import Tenant
    from django.contrib import messages
    from django.core.cache import cache

    logger = logging.getLogger(__name__)

    # --- Validar permisos ---
    user_tenant = getattr(request.user, "tenant", None)
    if not user_tenant or user_tenant.name.lower() != "inntesec":
        messages.error(request, "No tienes permiso para cambiar de empresa.")
        return redirect("dashboard:dashboard")

    # --- Buscar tenant destino ---
    tenant = Tenant.objects.filter(id=tenant_id).first()
    if not tenant:
        messages.error(request, "El tenant seleccionado no existe.")
        return redirect("dashboard:dashboard")

    # --- Actualizar tenant activo en sesión ---
    request.session["tenant_id"] = tenant.id
    request.session["tenant_name"] = tenant.name
    logger.info("[SwitchTenant] %s cambió a tenant %s", request.user.username, tenant.name)

    # --- Limpiar caché ---
    cache.clear()
    logger.debug("[SwitchTenant] Caché limpiada tras cambio de tenant")

    # --- Detectar URL de origen ---
    next_url = (request.POST.get("next") or request.META.get("HTTP_REFERER") or "").strip()
    parsed = urlparse(next_url or "")
    referer = (request.META.get("HTTP_REFERER") or "").lower()
    logger.debug("[SwitchTenant] next_url: %s | referer: %s", next_url, referer)

    # --- Si la URL es interna válida, mantener la ruta actual ---
    if parsed.path and parsed.path.startswith("/"):
        logger.debug(f"[SwitchTenant] Redirigiendo a ruta interna: {parsed.path}")
        return HttpResponseRedirect(parsed.path)

    # --- Redirecciones según el origen ---
    if "/soar/incidentes" in referer:
        logger.debug("[SwitchTenant] Manteniendo en lista de incidentes SOAR")
        return redirect("soar_incidents:list")

    if "/dashboard-soar" in referer or "soar_dashboard" in referer:
        logger.debug("[SwitchTenant] Manteniendo en dashboard SOAR")
        return redirect("soar_dashboard:dashboard")

    if "/dashboard/realtime" in referer or "realtime" in referer:
        logger.debug("[SwitchTenant] Manteniendo en dashboard Realtime")
        return redirect("dashboard:dashboard_realtime")

    if "/dashboard/alarmsone" in referer or "alarmsone" in referer:
        logger.debug("[SwitchTenant] Manteniendo en dashboard AlarmasOne")
        return redirect("dashboard:dashboard_alarmsone")

    # --- Fallback final: dashboard principal ---
    try:
        current_path = request.META.get("PATH_INFO", "")
        origin = request.META.get("HTTP_ORIGIN") or request.build_absolute_uri("/")
        full_path = f"{origin}{current_path}" if current_path else request.build_absolute_uri("/")
        logger.debug(f"[SwitchTenant] Fallback: redirigiendo a la misma ruta ({full_path})")
        return HttpResponseRedirect(full_path)
    except Exception as e:
        logger.warning(f"[SwitchTenant] Fallback al dashboard por error ({e})")
        return redirect("dashboard:dashboard")