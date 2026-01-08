from __future__ import annotations

import logging
from typing import Iterable, Tuple, Optional
from datetime import datetime, timedelta

import pytz
from django.contrib.auth.decorators import login_required
from django.db.models import F, Value, TextField
from django.db.models.functions import Lower, Replace, Trim, Cast
from django.shortcuts import render
from django.utils.timezone import make_aware, is_aware
from django.apps import apps

from tenants.decorators import tenant_required, service_required
from tenants.models import Tenant
from .models import IaSoar

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
    start = (now - timedelta(days=30)).replace(hour=0, minute=0, second=0, microsecond=0)
    end = now
    return start, end


def _normalize_range(
    from_qs: Optional[str],
    to_qs: Optional[str],
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
# Ticket map (para hidratar "Asignado" en el modal del dashboard)
# ============================================================
def _first_existing_field(model, names: tuple[str, ...]) -> Optional[str]:
    try:
        existing = {f.name for f in model._meta.get_fields()}
    except Exception:
        return None
    for n in names:
        if n in existing:
            return n
    return None


def _get_ticket_model():
    # intenta varios nombres típicos, sin romper si cambia el modelo
    for model_name in ("SoarTicket", "Ticket"):
        try:
            return apps.get_model("soar_tickets", model_name)
        except LookupError:
            continue
    return None


def _build_ticket_map(tenant, alarm_ids: list[str]) -> dict:
    """
    Retorna:
      { "ALARM_ID": {"assigned": true, "assigned_name": "Nombre Apellido"} , ... }
    """
    Ticket = _get_ticket_model()
    if not Ticket or not alarm_ids:
        return {}

    alarm_field = _first_existing_field(Ticket, ("alarm_id", "alarmid", "alarm", "alarm_code"))
    if not alarm_field:
        return {}

    # FK del usuario asignado (según tu payload: assigned_to)
    assigned_fk = _first_existing_field(Ticket, ("assigned_to", "assignee", "owner"))

    # campo directo de nombre (por si existe)
    name_field = _first_existing_field(Ticket, ("assigned_to_name", "assigned_name", "ticket_name"))

    qs = Ticket.objects.all()

    # filtra por tenant si existe
    if tenant and hasattr(Ticket, "tenant_id"):
        qs = qs.filter(tenant_id=getattr(tenant, "id", None))

    # filtra por alarm_ids
    try:
        qs = qs.filter(**{f"{alarm_field}__in": alarm_ids})
    except Exception:
        return {}

    values_fields = [alarm_field]
    if name_field:
        values_fields.append(name_field)
    if assigned_fk:
        values_fields += [
            f"{assigned_fk}__first_name",
            f"{assigned_fk}__last_name",
            f"{assigned_fk}__username",
        ]

    out: dict[str, dict] = {}
    try:
        for r in qs.values(*values_fields):
            key = str(r.get(alarm_field) or "").strip()
            if not key:
                continue

            # nombre preferente: campo directo, si existe
            nm = (str(r.get(name_field) or "").strip() if name_field else "")
            if not nm and assigned_fk:
                fn = str(r.get(f"{assigned_fk}__first_name") or "").strip()
                ln = str(r.get(f"{assigned_fk}__last_name") or "").strip()
                nm = (f"{fn} {ln}").strip()
                if not nm:
                    nm = str(r.get(f"{assigned_fk}__username") or "").strip()

            if key not in out:
                out[key] = {"assigned": True, "assigned_name": nm or ""}
    except Exception:
        logger.exception("[SOAR] Error construyendo ticket_map")
        return {}

    return out


# ============================================================
# Dashboard SOAR
# ============================================================
@login_required
@tenant_required
@service_required("alarms_one_id")
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

    # NUEVO: ticket_map para hidratar asignación en modal
    alarm_ids: list[str] = []
    try:
        alarm_ids = [str(r.get("alarm_id") or "").strip() for r in rows]
        alarm_ids = [x for x in alarm_ids if x]
        # opcional: evita duplicados
        alarm_ids = list(dict.fromkeys(alarm_ids))
    except Exception:
        alarm_ids = []

    ticket_map = {}
    try:
        ticket_map = _build_ticket_map(tenant, alarm_ids)
    except Exception:
        logger.exception("[SOAR] No se pudo construir ticket_map")
        ticket_map = {}

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

    # Países para whitelist (por tenant)
    selected_paises: list[str] = []
    try:
        effective_tenant_for_pref = tenant or getattr(request.user, "tenant", None)
        if effective_tenant_for_pref:
            pref = WhitelistCountryPreference.objects.filter(tenant=effective_tenant_for_pref).first()
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
        "whitelist_countries": ALL_COUNTRIES,
        "selected_paises": selected_paises,

        # NUEVO:
        "ticket_map": ticket_map,
    }
    return render(request, "soar_dashboard/dashboardsoar.html", ctx)
