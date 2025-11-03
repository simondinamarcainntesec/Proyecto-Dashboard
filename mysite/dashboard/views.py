from datetime import datetime, timedelta, timezone
import logging
import pytz
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.csrf import csrf_protect

from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.cache import never_cache
from django.core.cache import cache
from django.db.models import Count
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST

from tenants.decorators import tenant_required
from tenants.models import Tenant

from .charts import (
    build_trend_data,
    build_trend_by_device,
    build_donut_data,
    build_device_bar_data,
    build_action_bar_data,
    build_kpis,
    build_trend_by_action,
    build_device_by_action,
    build_hour_filter_payload,
    build_msg_severity_bar_data,
    build_trend_by_msg_severity,
    build_level_bar_data,
    build_subtype_bar_data,
    build_log_description_bar_data,
    build_trend_by_level,
    build_level_counts_by_hour,
    build_subtype_counts_by_level,
    build_trend_by_subtype,
    build_subtype_counts_by_hour,
    build_level_counts_by_subtype,
    build_msg_severity_by_level,
    build_msg_severity_by_subtype,
    build_level_by_msg_severity,
    build_subtype_by_msg_severity,
    build_hour_series_by_subtype,
    make_base_qs,
    _norm_dev,
)

logger = logging.getLogger(__name__)
CL_TZ = pytz.timezone("America/Santiago")


def _localize_naive(dt_naive):
    return CL_TZ.localize(dt_naive).astimezone(timezone.utc)


def _parse_local_any(s: str):
    if not s:
        return None, None
    s = s.strip()

    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            dt_local = datetime.strptime(s, fmt)
            return _localize_naive(dt_local), "datetime"
        except Exception:
            pass

    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%Y/%m/%d", "%d/%m/%Y"):
        try:
            d = datetime.strptime(s, fmt).date()
            start_local = datetime(d.year, d.month, d.day, 0, 0, 0)
            return _localize_naive(start_local), "date"
        except Exception:
            pass

    return None, None


@never_cache
@tenant_required
def dashboard_view(request):
    tenant = request.tenant
    now_utc = datetime.now(timezone.utc)

    raw_from = (request.GET.get("from") or "").strip()
    raw_to = (request.GET.get("to") or "").strip()
    parsed_from_utc, kind_from = _parse_local_any(raw_from)
    parsed_to_utc, kind_to = _parse_local_any(raw_to)

    dt_from_utc = now_utc - timedelta(days=7)
    dt_to_utc_exclusive = now_utc + timedelta(seconds=1)

    if raw_from or raw_to:
        if parsed_from_utc and parsed_to_utc:
            dt_from_utc = parsed_from_utc
            dt_to_utc_exclusive = parsed_to_utc + (
                timedelta(seconds=1) if kind_to == "datetime" else timedelta(days=1)
            )
        elif parsed_from_utc and not parsed_to_utc:
            dt_from_utc = parsed_from_utc
        elif parsed_to_utc and not parsed_from_utc:
            dt_to_utc_exclusive = parsed_to_utc + (
                timedelta(seconds=1) if kind_to == "datetime" else timedelta(days=1)
            )
            dt_from_utc = dt_to_utc_exclusive - timedelta(days=30)

    if dt_from_utc >= dt_to_utc_exclusive:
        dt_to_utc_exclusive = dt_from_utc + timedelta(days=1)

    def utc_to_local_date_str(dt_utc):
        return dt_utc.astimezone(CL_TZ).date().isoformat()

    from_date_str = raw_from or utc_to_local_date_str(dt_from_utc)
    to_date_str = raw_to or utc_to_local_date_str(dt_to_utc_exclusive)

    def _key(suffix: str) -> str:
        tid = getattr(tenant, "id", "none")
        return f"dash:{tid}:{dt_from_utc.isoformat()}:{dt_to_utc_exclusive.isoformat()}:{suffix}"

    delta_days = (dt_to_utc_exclusive - dt_from_utc).days
    is_heavy = delta_days >= 20
    ttl = 300 if is_heavy else 15

    context = cache.get(_key("ctx"))
    if context is None:
        qs_base = make_base_qs(dt_from_utc, dt_to_utc_exclusive)

        # === datasets y KPIs ===
        trend = build_trend_data(dt_from_utc, dt_to_utc_exclusive, qs_base=qs_base)
        trend_dev = build_trend_by_device(dt_from_utc, dt_to_utc_exclusive, top_n=10, qs_base=qs_base)
        trend_act = build_trend_by_action(dt_from_utc, dt_to_utc_exclusive, qs_base=qs_base)
        severity_counts = build_donut_data(dt_from_utc, dt_to_utc_exclusive, qs_base=qs_base)
        device_counts_top, device_by_sev, device_by_sev_full = build_device_bar_data(
            dt_from_utc, dt_to_utc_exclusive, top_n=10, qs_base=qs_base
        )
        action_counts, action_by_sev, action_by_device = build_action_bar_data(
            dt_from_utc, dt_to_utc_exclusive, top_n=10, qs_base=qs_base
        )
        device_by_action = build_device_by_action(dt_from_utc, dt_to_utc_exclusive, top_n=10, qs_base=qs_base)
        kpis = build_kpis(dt_from_utc, dt_to_utc_exclusive, qs_base=qs_base)
        hour_payload = build_hour_filter_payload(dt_from_utc, dt_to_utc_exclusive, top_n=10, qs_base=qs_base)
        (
            msg_severity_counts,
            device_counts_by_msg_severity,
            action_counts_by_msg_severity,
            severity_counts_by_msg_severity,
            msg_severity_counts_by_hour,
        ) = build_msg_severity_bar_data(dt_from_utc, dt_to_utc_exclusive, top_n=10, qs_base=qs_base)
        trend_msgsev = build_trend_by_msg_severity(dt_from_utc, dt_to_utc_exclusive, qs_base=qs_base)
        (
            level_counts,
            device_counts_by_level,
            action_counts_by_level,
            severity_counts_by_level,
        ) = build_level_bar_data(dt_from_utc, dt_to_utc_exclusive, top_n=10, qs_base=qs_base)
        (
            subtype_counts,
            device_counts_by_subtype,
            action_counts_by_subtype,
            severity_counts_by_subtype,
        ) = build_subtype_bar_data(dt_from_utc, dt_to_utc_exclusive, top_n=10, qs_base=qs_base)
        (
            logdesc_counts,
            device_counts_by_logdesc,
            action_counts_by_logdesc,
            severity_counts_by_logdesc,
        ) = build_log_description_bar_data(dt_from_utc, dt_to_utc_exclusive, top_n=10, qs_base=qs_base)
        msgsev_by_level = build_msg_severity_by_level(dt_from_utc, dt_to_utc_exclusive, qs_base=qs_base)
        msgsev_by_subtype = build_msg_severity_by_subtype(dt_from_utc, dt_to_utc_exclusive, qs_base=qs_base)
        trend_level = build_trend_by_level(dt_from_utc, dt_to_utc_exclusive, qs_base=qs_base)
        level_by_hour = build_level_counts_by_hour(dt_from_utc, dt_to_utc_exclusive, qs_base=qs_base)
        subtype_by_level = build_subtype_counts_by_level(dt_from_utc, dt_to_utc_exclusive, qs_base=qs_base)
        trend_st = build_trend_by_subtype(dt_from_utc, dt_to_utc_exclusive, qs_base=qs_base)
        subtype_counts_by_hour = build_subtype_counts_by_hour(dt_from_utc, dt_to_utc_exclusive, qs_base=qs_base)
        level_counts_by_subtype = build_level_counts_by_subtype(dt_from_utc, dt_to_utc_exclusive, top_n=None, qs_base=qs_base)
        level_by_msgsev = build_level_by_msg_severity(dt_from_utc, dt_to_utc_exclusive, qs_base=qs_base)
        subtype_by_msgsev = build_subtype_by_msg_severity(dt_from_utc, dt_to_utc_exclusive, qs_base=qs_base)
        hour_series_by_subtype = build_hour_series_by_subtype(dt_from_utc, dt_to_utc_exclusive, qs_base=qs_base)
        rows_all_devices = qs_base.values("device_name").annotate(total=Count("id")).order_by()
        device_counts_all = {_norm_dev(r["device_name"]): r["total"] for r in rows_all_devices}

        context = {
            "tenant": tenant,
            "trend_labels": trend["trend_labels"],
            "trend_data": trend["trend_data"],
            "severity_trends": trend["severity_trends"],
            "trend_by_device": trend_dev["trend_by_device"],
            "top_devices": trend_dev["top_devices"],
            "trend_by_action": trend_act["trend_by_action"],
            "trend_by_level": trend_level["trend_by_level"],
            "severity_counts": severity_counts,
            "device_counts": device_counts_all,
            "device_counts_top": device_counts_top,
            "action_counts": action_counts,
            "device_counts_by_severity": device_by_sev,
            "device_counts_by_severity_full": device_by_sev_full,
            "action_counts_by_severity": action_by_sev,
            "device_counts_by_action": device_by_action,
            "action_counts_by_device": action_by_device,
            "kpi_total": kpis["kpi_total"],
            "kpi_high": kpis["kpi_high"],
            "kpi_dispositivos": kpis["kpi_dispositivos"],
            "from_date_str": from_date_str,
            "to_date_str": to_date_str,
            "hour_labels": hour_payload["hour_labels"],
            "hour_data": hour_payload["hour_data"],
            "severity_counts_by_hour": hour_payload["severity_counts_by_hour"],
            "device_counts_by_hour": hour_payload["device_counts_by_hour"],
            "device_counts_by_hour_full": hour_payload["device_counts_by_hour_full"],
            "action_counts_by_hour": hour_payload["action_counts_by_hour"],
            "trend_labels_hour": hour_payload["trend_labels_hour"],
            "trend_by_hour": hour_payload["trend_by_hour"],
            "level_counts_by_hour": level_by_hour["level_counts_by_hour"],
            "msg_severity_counts": msg_severity_counts,
            "device_counts_by_msg_severity": device_counts_by_msg_severity,
            "action_counts_by_msg_severity": action_counts_by_msg_severity,
            "severity_counts_by_msg_severity": severity_counts_by_msg_severity,
            "msg_severity_counts_by_hour": msg_severity_counts_by_hour,
            "trend_by_msg_severity": trend_msgsev["trend_by_msg_severity"],
            "level_counts": level_counts,
            "device_counts_by_level": device_counts_by_level,
            "action_counts_by_level": action_counts_by_level,
            "severity_counts_by_level": severity_counts_by_level,
            "subtype_counts_by_level": subtype_by_level["subtype_counts_by_level"],
            "subtype_counts": subtype_counts,
            "device_counts_by_subtype": device_counts_by_subtype,
            "action_counts_by_subtype": action_counts_by_subtype,
            "severity_counts_by_subtype": severity_counts_by_subtype,
            "trend_by_subtype": trend_st["trend_by_subtype"],
            "subtype_counts_by_hour": subtype_counts_by_hour,
            "logdesc_counts": logdesc_counts,
            "device_counts_by_logdesc": device_counts_by_logdesc,
            "action_counts_by_logdesc": action_counts_by_logdesc,
            "severity_counts_by_logdesc": severity_counts_by_logdesc,
            "level_counts_by_subtype": level_counts_by_subtype,
            "msg_severity_by_level": msgsev_by_level["msg_severity_by_level"],
            "msg_severity_by_subtype": msgsev_by_subtype["msg_severity_by_subtype"],
            "level_by_msg_severity": level_by_msgsev["level_by_msg_severity"],
            "subtype_by_msg_severity": subtype_by_msgsev["subtype_by_msg_severity"],
            "hour_series_by_subtype": hour_series_by_subtype["hour_series_by_subtype"],
        }

        cache.set(_key("ctx"), context, timeout=ttl)

    # ✅ Mostrar selector siempre si el usuario pertenece a Inntesec
    user_tenant_name = getattr(getattr(request.user, "tenant", None), "name", "").lower()
    if user_tenant_name == "inntesec":
        context["all_tenants"] = Tenant.objects.all().order_by("name")

    resp = render(request, "dashboard/dashboard.html", context)
    resp["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    resp["Pragma"] = "no-cache"
    resp["Expires"] = "0"
    resp["Vary"] = "Cookie"
    return resp


# ==============
# 🔹 Cambio tenant
# ==============
@login_required
def switch_tenant(request, tenant_id):
    """
    Permite a usuarios de Inntesec cambiar de tenant desde cualquier dashboard.
    Redirige automáticamente al mismo módulo (SOAR, Realtime, Alarmas, etc.)
    y limpia la caché para evitar datos inconsistentes.
    """
    from tenants.models import Tenant
    from django.contrib import messages
    from django.core.cache import cache
    import logging

    logger = logging.getLogger(__name__)

    user_tenant = getattr(request.user, "tenant", None)
    if not user_tenant or user_tenant.name.lower() != "inntesec":
        messages.error(request, "No tienes permiso para cambiar de empresa.")
        return redirect("dashboard")

    # Buscar tenant destino
    tenant = Tenant.objects.filter(id=tenant_id).first()
    if not tenant:
        messages.error(request, "El tenant seleccionado no existe.")
        return redirect("dashboard")

    # Actualizar tenant activo en sesión
    request.session["tenant_id"] = tenant.id
    request.session["tenant_name"] = tenant.name
    logger.info("[SwitchTenant] %s cambió a tenant %s", request.user.username, tenant.name)

    # Limpiar caché para evitar gráficos antiguos
    cache.clear()
    logger.debug("[SwitchTenant] Caché limpiada tras cambio de tenant")

    # --- Detectar de dónde vino el cambio ---
    next_url = request.POST.get("next") or request.GET.get("next") or request.META.get("HTTP_REFERER", "")
    next_url = (next_url or "").lower()
    logger.debug("[SwitchTenant] next_url detectado: %s", next_url)

    # --- Redirecciones específicas ---
    if "/dashboard-soar/" in next_url or "soar_dashboard" in next_url:
        logger.debug("[SwitchTenant] Redirigiendo a SOAR dashboard")
        return redirect("soar_dashboard:dashboard")

    if "/dashboard/realtime" in next_url or "realtime" in next_url:
        logger.debug("[SwitchTenant] Redirigiendo a Realtime dashboard")
        return redirect("dashboard_realtime")

    if "/dashboard/alarmsone" in next_url or "alarmsone" in next_url:
        logger.debug("[SwitchTenant] Redirigiendo a Histórico Alarmas")
        return redirect("dashboard_alarmsone")

    # --- Respaldo con HTTP_REFERER si el 'next' venía vacío ---
    referer = (request.META.get("HTTP_REFERER") or "").lower()
    if "/dashboard-soar/" in referer or "soar_dashboard" in referer:
        return redirect("soar_dashboard:dashboard")
    if "/dashboard/realtime" in referer or "realtime" in referer:
        return redirect("dashboard_realtime")
    if "/dashboard/alarmsone" in referer or "alarmsone" in referer:
        return redirect("dashboard_alarmsone")

    # --- Fallback final ---
    logger.debug("[SwitchTenant] Sin origen detectado, redirigiendo al dashboard principal")
    return redirect("dashboard")