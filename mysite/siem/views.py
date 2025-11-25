# siem/views.py
from __future__ import annotations

from datetime import datetime, date

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import render
from tenants.decorators import tenant_required
from tenants.models import Tenant

from .log360_service import obtener_alertas_logs360


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

    q = (request.GET.get("q") or "").strip()

    from_str = (request.GET.get("from") or "").strip()
    to_str = (request.GET.get("to") or "").strip()

    from_date = _parse_date(from_str)
    to_date = _parse_date(to_str)

    if not to_date or not from_date:
        today = datetime.now().date()
        if not to_date:
            to_date = today
        if not from_date:
            # por defecto mostrar desde el día anterior, igual que el cURL que probaste
            from_date = today

    alerts = []
    error = None
    start_time = ""
    end_time = ""
    siem_account_id = ""

    if service_enabled:
        alerts, error, start_time, end_time, siem_account_id = obtener_alertas_logs360(
            query=q,
            account_id=siem_id,
            from_date=from_date,
            to_date=to_date,
        )

    paginator = Paginator(alerts, 50)
    page_obj = paginator.get_page(request.GET.get("page") or 1)

    context = {
        "tenant": tenant,
        "all_tenants": tenants_list,

        "has_siem": service_enabled,

        "alerts": alerts,
        "alerts_total": len(alerts),
        "page_obj": page_obj,
        "error": error,
        "q": q,

        "from_date_str": from_date.strftime("%Y-%m-%d") if from_date else "",
        "to_date_str": to_date.strftime("%Y-%m-%d") if to_date else "",

        "start_time": start_time,
        "end_time": end_time,
        "logs360_account_id": siem_account_id,
    }
    return render(request, "siem/alerts_list.html", context)
