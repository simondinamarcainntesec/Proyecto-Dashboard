from __future__ import annotations
from datetime import datetime, timedelta
import csv
import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q, F, Value, TextField
from django.db.models.functions import Lower, Replace, Trim, Cast
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.shortcuts import render, redirect
from django.views.decorators.http import require_GET
from tenants.decorators import tenant_required
from tenants.models import Tenant
from urllib.parse import urlparse

from .models import IncidenteSOAR

# 👇 NUEVO: credenciales de blacklist/portal
from home.models import TenantCredentials  # noqa

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
    for ch in ["{", "}", "[", "]", '"', "'", " "]:
        out = out.replace(ch, "")
    return out.lower()


def _normalize_tenant_aotag(tenant) -> str:
    raw = getattr(tenant, "alarms_one_id", "") or ""
    return _normalize_string_local(raw)


def _annotate_norm_aotag(qs):
    cleaned = Cast(F("aotag"), TextField())
    for ch in ["{", "}", "[", "]", '"', "'", " "]:
        cleaned = Replace(cleaned, Value(ch), Value(""), output_field=TextField())
    cleaned = Trim(cleaned, output_field=TextField())
    cleaned = Lower(cleaned, output_field=TextField())
    return qs.annotate(norm_aotag=cleaned)


# ---------- helper: queryset filtrado compartido (lista + export) ----------
def _build_incidents_queryset(request):
    """
    Construye el queryset de IncidenteSOAR aplicando:
    - tenant actual
    - rango de fechas (por defecto últimos 30 días)
    - búsqueda libre ?q=
    Devuelve: (qs, tenant, from_date, to_date, q_str)
    """
    q = (request.GET.get("q") or "").strip()

    today = datetime.now().date()
    default_from = today - timedelta(days=30)
    from_q = _parse_date(request.GET.get("from")) or default_from
    to_q = _parse_date(request.GET.get("to")) or today

    qs = IncidenteSOAR.objects.all()

    # filtro por TENANT
    tenant = getattr(request, "tenant", None)
    norm_tid = _normalize_tenant_aotag(tenant) if tenant else ""
    if norm_tid:
        qs = _annotate_norm_aotag(qs).filter(norm_aotag=norm_tid)
    else:
        qs = qs.none()

    # rango de fechas
    qs = qs.filter(date__gte=from_q, date__lte=to_q)

    # búsqueda libre
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
    return qs, tenant, from_q, to_q, q


# ---------- helpers export CSV ----------
def _slugify_name(value: str | None) -> str:
    if not value:
        return "tenant"
    value = value.lower()
    out = []
    for ch in value:
        if ch.isalnum():
            out.append(ch)
        else:
            out.append("_")
    slug = "".join(out)
    while "__" in slug:
        slug = slug.replace("__", "_")
    slug = slug.strip("_")
    return slug or "tenant"


def _make_incidents_csv_response(iterable, tenant, scope: str) -> HttpResponse:
    """
    Genera un HttpResponse CSV a partir de un iterable de IncidenteSOAR.
    scope: 'page' o 'all' sólo para el nombre del archivo.
    """
    tenant_name = getattr(tenant, "name", "") or ""
    tenant_slug = _slugify_name(tenant_name)
    today_str = datetime.now().strftime("%Y%m%d")
    filename = f"soar_incidentes_{tenant_slug}_{scope}_{today_str}.csv"

    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'

    writer = csv.writer(response)
    # Cabecera: enfocada en resumen, fecha/hora, severidad e ID
    writer.writerow(
        [
            "Alarm ID",
            "Fecha",
            "Hora",
            "Tenant",
            "Nivel severidad",
            "Tipo de amenaza",
            "Dispositivo",
            "Resumen",
            "Descripción incidente",
            "Riesgo detectado",
            "Análisis criticidad",
            "Medidas correctivas",
            "Application",
            "AO Tag",
        ]
    )

    # Iteramos de forma eficiente (por si son muchos registros)
    for it in iterable:
        date_str = it.date.isoformat() if getattr(it, "date", None) else ""
        time_obj = getattr(it, "time", None)
        time_str = time_obj.strftime("%H:%M:%S") if time_obj else ""

        writer.writerow(
            [
                getattr(it, "alarmd_id", "") or "",
                date_str,
                time_str,
                tenant_name,
                getattr(it, "nivel_de_severidad", "") or "",
                getattr(it, "tipo_de_amenaza", "") or "",
                getattr(it, "dispositivo", "") or "",
                getattr(it, "resumen_humano", "") or "",
                getattr(it, "descripcion_incidente", "") or "",
                getattr(it, "riego_detectado", "") or "",
                getattr(it, "analisis_criticidad", "") or "",
                getattr(it, "medidas_correctivas", "") or "",
                getattr(it, "application", "") or "",
                getattr(it, "aotag", "") or "",
            ]
        )

    return response


# ---------- vista principal ----------
@login_required
@tenant_required
def incidents_list(request):
    qs, tenant, from_q, to_q, q = _build_incidents_queryset(request)

    paginator = Paginator(qs, 25)
    page_obj = paginator.get_page(request.GET.get("page"))

    # 👇 NUEVO: obtener credenciales activas del tenant (para el modal)
    cred = None
    try:
        if tenant:
            cred = TenantCredentials.get_active_for_tenant(int(getattr(tenant, "id", 0)))
    except Exception as e:
        logger.exception("[SOAR_INCIDENTS] Error obteniendo credenciales del tenant: %s", e)

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
        "cred": cred,  # 👈 para el partial de credenciales
    }
    return render(request, "soar_incidents/list.html", context)


# ---------- export CSV: página actual ----------
@login_required
@tenant_required
def export_csv_current(request):
    """
    Exporta a CSV sólo los incidentes que se muestran en la página actual
    (respeta filtros de fecha y búsqueda).
    """
    qs, tenant, from_q, to_q, q = _build_incidents_queryset(request)

    paginator = Paginator(qs, 25)
    page_obj = paginator.get_page(request.GET.get("page"))

    # page_obj.object_list es un queryset/iterable con los elementos de la página
    return _make_incidents_csv_response(page_obj.object_list, tenant, scope="page")


# ---------- export CSV: todos los incidentes del rango ----------
@login_required
@tenant_required
def export_csv_all(request):
    """
    Exporta a CSV todos los incidentes del rango filtrado (todas las páginas).
    """
    qs, tenant, from_q, to_q, q = _build_incidents_queryset(request)

    # Usamos iterator() por si son muchos registros
    return _make_incidents_csv_response(qs.iterator(), tenant, scope="all")


# ---------- cambio de tenant ----------
@login_required
def switch_tenant(request, tenant_id):
    """
    Permite a usuarios de Inntesec cambiar de tenant desde cualquier dashboard.
    Mantiene al usuario en el mismo módulo tras el cambio y limpia la caché.
    """
    from tenants.models import Tenant
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


# ---------- API JSON: incidentes por alarm_ids (para el modal del dashboard) ----------
@login_required
@tenant_required
@require_GET
def api_incidents_by_alarm_ids(request):
    """
    Devuelve incidentes de IncidenteSOAR pertenecientes al tenant activo,
    filtrados por ?alarm_ids=ID1,ID2,ID3
    """
    tenant = getattr(request, "tenant", None)
    norm_tid = _normalize_tenant_aotag(tenant) if tenant else ""
    if not norm_tid:
        return JsonResponse([], safe=False)

    raw_ids = (request.GET.get("alarm_ids") or "").strip()
    alarm_ids = [s for s in (raw_ids.split(",") if raw_ids else []) if s]
    if not alarm_ids:
        return JsonResponse([], safe=False)

    try:
        qs = IncidenteSOAR.objects.all()
        qs = _annotate_norm_aotag(qs).filter(norm_aotag=norm_tid)
        qs = qs.filter(alarmd_id__in=alarm_ids).order_by("-date", "-time")[:1000]

        data = list(
            qs.values(
                "alarmd_id",
                "aotag",
                "dispositivo",
                "descripcion_incidente",
                "tipo_de_amenaza",
                "nivel_de_severidad",
                "medidas_correctivas",
                "resumen_humano",
                "riego_detectado",
                "analisis_criticidad",
                "date",
                "time",
                "application",
            )
        )
        return JsonResponse(data, safe=False)
    except Exception as e:
        logger.exception("[api_by_alarm_ids] Error: %s", e)
        # 200 con [] evita alertas en el front; el modal abre vacío.
        return JsonResponse([], safe=False)
