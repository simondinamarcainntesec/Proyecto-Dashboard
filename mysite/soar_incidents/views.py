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
from django.views.decorators.http import require_GET, require_POST
from tenants.decorators import tenant_required, service_required
from tenants.models import Tenant, TenantUser
from urllib.parse import urlparse
from django.db import IntegrityError
from .models import IncidenteSOAR

# credenciales de blacklist/portal + preferencias de países
from home.models import TenantCredentials, WhitelistCountryPreference  # noqa
from home.countries import ALL_COUNTRIES

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




@login_required
@tenant_required
@service_required("alarms_one_id")
def incidents_list(request):
    qs, tenant, from_q, to_q, q = _build_incidents_queryset(request)

    # ==============================
    # ✅ NUEVO: filtros combinables (sev + assigned)
    # ==============================
    sev_filter = (request.GET.get("sev") or "").strip().lower()          # low|medium|high|critical|""
    assigned_filter = (request.GET.get("assigned") or "").strip().lower()  # yes|no|""

    # ---- helper para severidad (robusto con ES/EN)
    def _sev_q(sev_key: str):
        if sev_key == "critical":
            vals = ["critical", "crítico", "critico"]
        elif sev_key == "high":
            vals = ["high", "alto"]
        elif sev_key == "medium":
            vals = ["medium", "medio"]
        elif sev_key == "low":
            vals = ["low", "bajo"]
        else:
            vals = []

        qq = Q()
        for v in vals:
            qq |= Q(nivel_de_severidad__iexact=v)
        return qq

    # ---- aplicar filtro severidad
    if sev_filter in ("low", "medium", "high", "critical"):
        if hasattr(qs, "filter"):
            qs = qs.filter(_sev_q(sev_filter))
        else:
            # qs es lista (fallback)
            def norm(s):
                return (str(s or "").strip().lower()
                        .replace("í", "i").replace("ó", "o").replace("á", "a").replace("é", "e").replace("ú", "u"))

            wanted = {
                "critical": {"critical", "critico"},
                "high": {"high", "alto"},
                "medium": {"medium", "medio"},
                "low": {"low", "bajo"},
            }[sev_filter]

            qs = [it for it in qs if norm(getattr(it, "nivel_de_severidad", "")) in wanted]

    # ---- aplicar filtro asignación (ticket existe OPEN o CLOSED)
    if assigned_filter in ("yes", "no"):
        try:
            from soar_tickets.models import SoarTicket

            if tenant:
                if hasattr(qs, "filter"):
                    ticket_alarm_ids_qs = SoarTicket.objects.filter(
                        tenant_id=tenant.id
                    ).values_list("alarm_id", flat=True)

                    if assigned_filter == "yes":
                        qs = qs.filter(alarmd_id__in=ticket_alarm_ids_qs)
                    else:
                        qs = qs.exclude(alarmd_id__in=ticket_alarm_ids_qs)
                else:
                    # qs es lista: limitamos consulta solo a alarm_ids presentes
                    alarm_ids_all = [
                        str(getattr(it, "alarmd_id", "")).strip()
                        for it in qs
                        if getattr(it, "alarmd_id", None)
                    ]
                    alarm_ids_all = [x for x in alarm_ids_all if x]

                    ticket_alarm_ids = set()
                    if alarm_ids_all:
                        ticket_alarm_ids = set(
                            SoarTicket.objects.filter(
                                tenant_id=tenant.id,
                                alarm_id__in=alarm_ids_all
                            ).values_list("alarm_id", flat=True)
                        )
                        ticket_alarm_ids = {str(x).strip() for x in ticket_alarm_ids if x is not None}

                    if assigned_filter == "yes":
                        qs = [it for it in qs if str(getattr(it, "alarmd_id", "")).strip() in ticket_alarm_ids]
                    else:
                        qs = [it for it in qs if str(getattr(it, "alarmd_id", "")).strip() not in ticket_alarm_ids]

        except Exception as e:
            logger.exception("[SOAR_INCIDENTS] Error aplicando filtro assigned: %s", e)

    # ==============================
    # Paginación
    # ==============================
    paginator = Paginator(qs, 25)
    page_obj = paginator.get_page(request.GET.get("page"))

    # ==============================
    # ✅ IDs asignados (tickets OPEN o CLOSED) para los eventos de ESTA página
    # ==============================
    assigned_alarm_ids = set()
    try:
        from soar_tickets.models import SoarTicket

        if tenant and page_obj and page_obj.object_list:
            alarm_ids_page = [
                str(getattr(it, "alarmd_id", "")).strip()
                for it in page_obj.object_list
                if getattr(it, "alarmd_id", None)
            ]
            alarm_ids_page = [x for x in alarm_ids_page if x]

            if alarm_ids_page:
                assigned_alarm_ids = set(
                    SoarTicket.objects.filter(
                        tenant_id=tenant.id,
                        alarm_id__in=alarm_ids_page,
                    ).values_list("alarm_id", flat=True)
                )
                assigned_alarm_ids = {str(x).strip() for x in assigned_alarm_ids if x is not None}

    except Exception as e:
        logger.exception("[SOAR_INCIDENTS] Error calculando assigned_alarm_ids: %s", e)
        assigned_alarm_ids = set()

    # ==============================
    # credenciales activas del tenant (para el modal)
    # ==============================
    cred = None
    try:
        if tenant:
            cred = TenantCredentials.get_active_for_tenant(int(getattr(tenant, "id", 0)))
    except Exception as e:
        logger.exception("[SOAR_INCIDENTS] Error obteniendo credenciales del tenant: %s", e)

    # Selector solo visible si el usuario pertenece a Inntesec
    tenants_list = []
    user_tenant = getattr(request.user, "tenant", None)
    if user_tenant and user_tenant.name.lower() == "inntesec":
        tenants_list = Tenant.objects.all().order_by("name")

    # Países para el modal de whitelist (POR TENANT, NO POR USER)
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
        logger.exception("[SOAR_INCIDENTS] Error leyendo preferencias de países (tenant): %s", e)
        selected_paises = []

    # ✅ para paginación sin perder filtros
    params = request.GET.copy()
    params.pop("page", None)
    base_qs = params.urlencode()

    context = {
        "page_obj": page_obj,
        "q": q,
        "total": paginator.count,
        "from_date_str": from_q.strftime("%Y-%m-%d"),
        "to_date_str": to_q.strftime("%Y-%m-%d"),
        "tenant": tenant,
        "all_tenants": tenants_list,
        "cred": cred,
        "whitelist_countries": ALL_COUNTRIES,
        "selected_paises": selected_paises,

        # ✅ NUEVO
        "assigned_alarm_ids": assigned_alarm_ids,
        "sev_filter": sev_filter,
        "assigned_filter": assigned_filter,
        "base_qs": base_qs,
    }
    return render(request, "soar_incidents/list.html", context)




# ---------- export CSV: página actual ----------
@login_required
@tenant_required
@service_required("alarms_one_id")
def export_csv_current(request):
    """
    Exporta a CSV sólo los incidentes que se muestran en la página actual
    (respeta filtros de fecha y búsqueda).
    """
    qs, tenant, from_q, to_q, q = _build_incidents_queryset(request)

    paginator = Paginator(qs, 25)
    page_obj = paginator.get_page(request.GET.get("page"))

    return _make_incidents_csv_response(page_obj.object_list, tenant, scope="page")


# ---------- export CSV: todos los incidentes del rango ----------
@login_required
@tenant_required
@service_required("alarms_one_id")
def export_csv_all(request):
    """
    Exporta a CSV todos los incidentes del rango filtrado (todas las páginas).
    """
    qs, tenant, from_q, to_q, q = _build_incidents_queryset(request)
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

    user_tenant = getattr(request.user, "tenant", None)
    if not user_tenant or user_tenant.name.lower() != "inntesec":
        messages.error(request, "No tienes permiso para cambiar de empresa.")
        return redirect("dashboard:dashboard")

    tenant = Tenant.objects.filter(id=tenant_id).first()
    if not tenant:
        messages.error(request, "El tenant seleccionado no existe.")
        return redirect("dashboard:dashboard")

    request.session["tenant_id"] = tenant.id
    request.session["tenant_name"] = tenant.name
    logger.info("[SwitchTenant] %s cambió a tenant %s", request.user.username, tenant.name)

    cache.clear()
    logger.debug("[SwitchTenant] Caché limpiada tras cambio de tenant")

    next_url = (request.POST.get("next") or request.META.get("HTTP_REFERER") or "").strip()
    parsed = urlparse(next_url or "")
    referer = (request.META.get("HTTP_REFERER") or "").lower()
    logger.debug("[SwitchTenant] next_url: %s | referer: %s", next_url, referer)

    if parsed.path and parsed.path.startswith("/"):
        logger.debug("[SwitchTenant] Redirigiendo a ruta interna: %s", parsed.path)
        return HttpResponseRedirect(parsed.path)

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

    try:
        current_path = request.META.get("PATH_INFO", "")
        origin = request.META.get("HTTP_ORIGIN") or request.build_absolute_uri("/")
        full_path = f"{origin}{current_path}" if current_path else request.build_absolute_uri("/")
        logger.debug("[SwitchTenant] Fallback: redirigiendo a la misma ruta (%s)", full_path)
        return HttpResponseRedirect(full_path)
    except Exception as e:
        logger.warning("[SwitchTenant] Fallback al dashboard por error (%s)", e)
        return redirect("dashboard:dashboard")


# ---------- API JSON: incidentes por alarm_ids (para el modal del dashboard) ----------
@require_GET
@login_required
@tenant_required
@service_required("alarms_one_id")
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
        return JsonResponse([], safe=False)

def _is_inntesec_user(request) -> bool:
    try:
        ut = getattr(request.user, "tenant", None)
        return bool(ut and (ut.name or "").strip().lower() == "inntesec")
    except Exception:
        return False


def _get_active_tenant(request):
    """
    Resuelve tenant efectivo con prioridad:
    1) request.tenant (middleware/decorator tenant_required)
    2) session['tenant_id'] / session['active_tenant_id']
    3) request.user.tenant
    """
    t = getattr(request, "tenant", None)
    if t:
        return t

    tid = request.session.get("tenant_id") or request.session.get("active_tenant_id")
    if tid:
        try:
            return Tenant.objects.filter(id=int(tid)).first()
        except Exception:
            return None

    return getattr(request.user, "tenant", None)


def _serialize_tenant_user(u: TenantUser) -> dict:
    full = (f"{u.first_name or ''} {u.last_name or ''}").strip()
    if not full:
        full = u.username or f"User {u.id}"
    return {
        "id": u.id,
        "full_name": full,
        "username": u.username or "",
        "email": u.email or "",
    }


@login_required
@tenant_required
@require_POST
def api_tenant_users(request):
    """
    POST JSON:
      {"tenant_id": 123}  # solo Inntesec puede solicitar otro tenant
    RESP:
      {"users": [{id, full_name, username, email}, ...]}
    """
    try:
        payload = json.loads((request.body or b"{}").decode("utf-8"))
    except Exception:
        payload = {}

    tenant = None

    # Inntesec puede elegir tenant explícito
    if _is_inntesec_user(request):
        tid = payload.get("tenant_id")
        if tid:
            tenant = Tenant.objects.filter(id=int(tid)).first()

    # resto: siempre tenant activo
    if tenant is None:
        tenant = _get_active_tenant(request)

    if not tenant:
        return JsonResponse({"users": []}, status=200)

    try:
        qs = (
            TenantUser.objects
            .filter(tenant_id=tenant.id, is_active=True)
            .order_by("first_name", "last_name", "username")
        )

        users = [_serialize_tenant_user(u) for u in qs]
        return JsonResponse({"users": users}, status=200)

    except Exception as e:
        logger.exception("[SOAR] api_tenant_users error: %s", e)
        return JsonResponse({"users": []}, status=200)