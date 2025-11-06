from __future__ import annotations
import logging
from typing import Iterable, Tuple, Optional
from datetime import datetime, timedelta, time as dtime

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

logger = logging.getLogger(__name__)
CL_TZ = pytz.timezone("America/Santiago")

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

# ============
# Fechas
# ============
def _parse_iso_dt_local(s: str) -> Optional[datetime]:
    """
    Acepta 'YYYY-MM-DD' o 'YYYY-MM-DDTHH:MM:SS'. Devuelve datetime AWARE en America/Santiago.
    """
    if not s:
        return None
    s = s.strip().replace(" ", "T")
    try:
        # Soporta ambos formatos
        if "T" in s:
            dt = datetime.fromisoformat(s)
        else:
            # sólo fecha
            dt = datetime.fromisoformat(s + "T00:00:00")
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

def _normalize_range(from_qs: Optional[str], to_qs: Optional[str]) -> Tuple[datetime, datetime, str, str]:
    """
    Resuelve el rango efectivo y strings para inputs <input type=date>.
    - Si no vienen params, últimos 30 días.
    - 'from' se lleva al inicio del día local, 'to' al final del día local.
    """
    if not from_qs and not to_qs:
        f, t = _default_range_now_30d()
    else:
        f = _parse_iso_dt_local(from_qs) or _default_range_now_30d()[0]
        t = _parse_iso_dt_local(to_qs) or _default_range_now_30d()[1]

    # normalizamos a [00:00:00, 23:59:59]
    f = f.replace(hour=0, minute=0, second=0, microsecond=0)
    t = t.replace(hour=23, minute=59, second=59, microsecond=0)

    # para inputs date (YYYY-MM-DD)
    from_date_str = f.strftime("%Y-%m-%d")
    to_date_str = t.strftime("%Y-%m-%d")
    return f, t, from_date_str, to_date_str

# ============================================================
# 🧩 Dashboard SOAR (principal)
# ============================================================
@login_required
@tenant_required
def dashboard_soar(request):
    """
    Renderiza el panel SOAR filtrado por tenant y rango de fechas (?from=&to=).
    Si el usuario pertenece a Inntesec, muestra el selector de tenants.
    """
    tenant = getattr(request, "tenant", None)
    norm_tid = _normalize_tenant_aotag(tenant) if tenant else ""

    # === Rango de fechas desde la query ===
    q_from = request.GET.get("from")  # 'YYYY-MM-DD' o 'YYYY-MM-DDTHH:MM:SS'
    q_to = request.GET.get("to")
    f_dt, t_dt, from_date_str, to_date_str = _normalize_range(q_from, q_to)

    logger.info(
        "[SOAR] dashboard_soar | tenant=%s | aoid(raw)=%s norm=%s | from=%s to=%s",
        getattr(tenant, "name", None),
        getattr(tenant, "alarms_one_id", None),
        norm_tid,
        f_dt.isoformat(),
        t_dt.isoformat(),
    )

    rows: Iterable[dict] = []
    try:
        qs = IaSoar.objects.all()

        # Tenant
        if norm_tid:
            qs = _annotate_norm_aotag(qs).filter(norm_aotag=norm_tid)
        else:
            logger.warning("[SOAR] request sin tenant o sin alarms_one_id -> 0 filas")
            qs = qs.none()

        # === Filtro por fechas ===
        # Preferencia 1: si tienes un DateTimeField 'timestamp' en IaSoar
        # Preferencia 2: si 'date' es DateField (o string ISO YYYY-MM-DD), filtramos por 'date'
        # Preferencia 3: si tienes 'date' y 'time' separados, filtramos sólo por 'date' (rango de días)
        has_timestamp = hasattr(IaSoar, "timestamp")
        if has_timestamp:
            qs = qs.filter(timestamp__gte=f_dt, timestamp__lte=t_dt)
        else:
            # Usamos sólo 'date' (asumiendo ISO) – si es TextField en ISO también sirve por orden lexicográfico
            qs = qs.filter(date__gte=f_dt.date(), date__lte=t_dt.date())

        # Limitar (ajusta a tus necesidades)
        qs = qs.order_by("-date")[:20000]

        # 🔴 IMPORTANTE: incluimos "Application" para el gráfico de aplicaciones
        rows = list(
            qs.values(
                "date", "time",
                "device", "service", "proto",
                "srccountry",
                "srcip", "dstip",
                "aotag",
                "severity",
                "security_action",
                "action",
                "Application",   # <- campo nuevo
            )
        )

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
        # Para la barra de fechas (como en el histórico)
        "from_date_str": from_date_str,
        "to_date_str": to_date_str,
        "request": request,
    }
    return render(request, "soar_dashboard/dashboardsoar.html", ctx)

# ============================================================
# 🧩 Cambio de Tenant universal
# ============================================================
@login_required
def switch_tenant(request, tenant_id):
    user_tenant = getattr(request.user, "tenant", None)
    if not user_tenant or user_tenant.name.lower() != "inntesec":
        messages.error(request, "No tienes permiso para cambiar de empresa.")
        return redirect("dashboard")

    tenant = Tenant.objects.filter(id=tenant_id).first()
    if not tenant:
        messages.error(request, "El tenant seleccionado no existe.")
        return redirect("dashboard")

    request.session["tenant_id"] = tenant.id
    request.session["tenant_name"] = tenant.name
    logger.info("[SwitchTenant] %s cambió a tenant %s", request.user.username, tenant.name)

    next_url = (
        request.POST.get("next")
        or request.GET.get("next")
        or request.META.get("HTTP_REFERER", "")
    ).lower()

    logger.debug("[SwitchTenant] next_url detectado: %s", next_url)

    if "dashboard-soar" in next_url:
        logger.debug("[SwitchTenant] Redirigiendo al dashboard SOAR")
        return redirect("soar_dashboard:dashboard")

    if "dashboard/realtime" in next_url or "realtime" in next_url:
        logger.debug("[SwitchTenant] Redirigiendo al dashboard Tiempo Real")
        return redirect("dashboard_realtime")

    if "dashboard/alarmsone" in next_url or "alarmsone" in next_url:
        logger.debug("[SwitchTenant] Redirigiendo al dashboard Histórico de Alarmas")
        return redirect("dashboard_alarmsone")

    referer = (request.META.get("HTTP_REFERER") or "").lower()
    logger.debug("[SwitchTenant] Referer=%s", referer)

    if "dashboard-soar" in referer:
        return redirect("soar_dashboard:dashboard")
    if "dashboard/realtime" in referer or "realtime" in referer:
        return redirect("dashboard_realtime")
    if "dashboard/alarmsone" in referer or "alarmsone" in referer:
        return redirect("dashboard_alarmsone")

    logger.debug("[SwitchTenant] No se detectó origen, redirigiendo al dashboard principal")
    return redirect("dashboard")
