import json
import os
import ssl
import urllib.request
from pathlib import Path
from typing import Any, List, Dict
from datetime import datetime, time

import requests
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils import timezone

from tenants.decorators import tenant_required
from tenants.models import Tenant, TenantUser, TenantDashboardEmbed
from .services import fetch_anomaly_summary, fetch_anomaly_by_monitor

# ✅ Preferencias de países (POR TENANT)
from home.models import WhitelistCountryPreference
from home.countries import ALL_COUNTRIES

import logging

logger = logging.getLogger(__name__)

SITE24X7_WEBHOOK_URL = os.environ.get("SITE24X7_WEBHOOK_URL")
SITE24X7_WEBHOOK_SECRET = os.environ.get("SITE24X7_WEBHOOK_SECRET")
SITE24X7_WEBHOOK_HEADER_NAME = os.environ.get("SITE24X7_WEBHOOK_HEADER_NAME", "passkey")

_raw_verify = (os.environ.get("SITE24X7_VERIFY_SSL", "True") or "").strip().lower()
SITE24X7_VERIFY_SSL = _raw_verify in ("1", "true", "yes", "y", "on")

TOKEN_FILE = Path(__file__).resolve().parent / "token.txt"

CANDIDATE_KEYS = {
    "acces_token",
    "access_token",
    "token",
    "access-token",
    "access token",
    "access_token".upper(),
    "access_token".title(),
    "access_token".capitalize(),
    "access_token".replace("_", ""),
    "access_token".replace("_", "-"),
}
CANDIDATE_KEYS.update(
    {
        "access_token",
        "access-token",
        "access token",
        "Access_Token",
        "ACCESS_TOKEN",
    }
)

SITE24X7_API_BASE_URL = os.environ.get("SITE24X7_API_BASE_URL", "https://www.site24x7.com/api")
CURRENT_STATUS_PATH = "/msp/customers/monitors/status"


# =========================
# Helpers tenant / prefs
# =========================
def _resolve_tenant(request):
    tenant = getattr(request, "tenant", None)
    if tenant is not None:
        return tenant

    tu = (
        TenantUser.objects
        .filter(user=request.user)
        .select_related("tenant")
        .first()
    )
    return tu.tenant if tu else None


def _tenants_list_for_user(user):
    user_tenant = getattr(user, "tenant", None)
    if user_tenant and getattr(user_tenant, "name", "").lower() == "inntesec":
        return Tenant.objects.all().order_by("name")
    return []


def _selected_paises_for_tenant(tenant):
    """
    ✅ Lee la preferencia desde WhitelistCountryPreference.tenant (NO existe field user).
    """
    try:
        if not tenant:
            return []
        pref = WhitelistCountryPreference.objects.filter(tenant=tenant).first()
        return (pref.paises or []) if pref else []
    except Exception as e:
        logger.exception("[SITE24X7] Error leyendo preferencias de países (tenant): %s", e)
        return []


# =========================
# Token helpers
# =========================
def collect_tokens(obj: Any) -> List[str]:
    found: List[str] = []
    if isinstance(obj, dict):
        lowered = {k.lower() for k in CANDIDATE_KEYS}
        for k, v in obj.items():
            if isinstance(k, str):
                key_norm = k.strip().lower()
                if key_norm in lowered and isinstance(v, str) and v.strip():
                    found.append(v.strip())
            found.extend(collect_tokens(v))
    elif isinstance(obj, list):
        for item in obj:
            found.extend(collect_tokens(item))
    return found


def get_site24x7_token() -> str:
    if not SITE24X7_WEBHOOK_URL:
        raise RuntimeError("SITE24X7_WEBHOOK_URL no está configurada.")
    if not SITE24X7_WEBHOOK_SECRET:
        raise RuntimeError("SITE24X7_WEBHOOK_SECRET no está configurada.")

    headers = {SITE24X7_WEBHOOK_HEADER_NAME: SITE24X7_WEBHOOK_SECRET}
    req = urllib.request.Request(url=SITE24X7_WEBHOOK_URL, method="GET", headers=headers)
    ctx = ssl.create_default_context() if SITE24X7_VERIFY_SSL else ssl._create_unverified_context()

    try:
        with urllib.request.urlopen(req, timeout=20, context=ctx) as resp:
            status = resp.getcode()
            body = resp.read()
    except Exception as e:
        raise RuntimeError(f"Error al llamar la API del webhook: {e}")

    text = body.decode("utf-8", errors="replace").strip()

    if status // 100 != 2:
        raise RuntimeError(f"Webhook respondió HTTP {status}")

    try:
        data = json.loads(text)
        tokens = collect_tokens(data)
        if not tokens:
            raise RuntimeError("No se encontraron tokens en el JSON del webhook.")
        chosen = tokens[2] if len(tokens) >= 3 else tokens[-1]

        try:
            TOKEN_FILE.write_text(chosen, encoding="utf-8")
        except Exception:
            pass

        return chosen

    except json.JSONDecodeError:
        if not text:
            raise RuntimeError("Respuesta vacía del webhook de token (no es JSON).")
        try:
            TOKEN_FILE.write_text(text, encoding="utf-8")
        except Exception:
            pass
        return text


# =========================
# Monitor status helpers
# =========================
def _parse_site24x7_timestamp(value: Any):
    if not value:
        return None

    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(value / 1000.0, tz=timezone.utc)
        except Exception:
            return None

    if isinstance(value, str):
        s = value.strip()
        if not s:
            return None

        if s.isdigit():
            try:
                return datetime.fromtimestamp(int(s) / 1000.0, tz=timezone.utc)
            except Exception:
                pass

        try:
            iso = s.replace("Z", "+00:00")
            dt = datetime.fromisoformat(iso)
            if timezone.is_naive(dt):
                dt = timezone.make_aware(dt, timezone.utc)
            return dt
        except Exception:
            pass

    return None


def _humanize_delta(delta):
    seconds = int(delta.total_seconds())
    if seconds < 60:
        return "Hace menos de 1 minuto"

    minutes = seconds // 60
    if minutes < 60:
        return f"Hace {minutes} minuto{'s' if minutes != 1 else ''}"

    hours = minutes // 60
    if hours < 24:
        return f"Hace {hours} hora{'s' if hours != 1 else ''}"

    days = hours // 24
    return f"Hace {days} día{'s' if days != 1 else ''}"


def format_last_polled(raw_value: Any) -> str:
    dt = _parse_site24x7_timestamp(raw_value)
    if not dt:
        return "—"

    now = timezone.now()
    if dt > now:
        return "Hace instantes"

    delta = now - dt
    return _humanize_delta(delta)


def fetch_customer_status(access_token: str, zaaid: str) -> Dict[str, Any]:
    headers = {
        "Accept": "application/json; version=2.0",
        "Authorization": f"Zoho-oauthtoken {access_token}",
    }

    url = f"{SITE24X7_API_BASE_URL}{CURRENT_STATUS_PATH}"
    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    customers = data.get("data", [])
    for customer in customers:
        if str(customer.get("zaaid")) == str(zaaid):
            return customer

    return {}


def build_counters(monitors: List[Dict[str, Any]]) -> Dict[str, int]:
    counters = {
        "down": 0,
        "up": 0,
        "trouble": 0,
        "critical": 0,
        "suspended": 0,
    }

    for m in monitors:
        st = m.get("status")
        if st == 0:
            counters["down"] += 1
        elif st == 1:
            counters["up"] += 1
        elif st == 2:
            counters["trouble"] += 1
        elif st == 3:
            counters["critical"] += 1
        elif st == 5:
            counters["suspended"] += 1

    return counters


# =========================
# Date filter helpers
# =========================
def _parse_ymd(s: str):
    s = (s or "").strip()
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
        return None


def _get_period_from_request(request, default=3) -> int:
    from_s = (request.GET.get("from") or "").strip()
    to_s = (request.GET.get("to") or "").strip()

    d1 = _parse_ymd(from_s) if from_s else None
    d2 = _parse_ymd(to_s) if to_s else None
    if d1 and d2:
        return 50

    periods = [p.strip() for p in request.GET.getlist("period") if (p or "").strip()]

    for p in periods:
        try:
            pi = int(p)
        except Exception:
            continue
        if pi in (2, 3, 5, 50):
            return pi

    try:
        default_i = int(default)
    except Exception:
        default_i = 3

    return default_i if default_i in (2, 3, 5, 50) else 3


def _get_custom_range_ms_from_request(request, period: int | None = None):
    if period != 50:
        return (None, None)

    from_s = (request.GET.get("from") or "").strip()
    to_s = (request.GET.get("to") or "").strip()

    d1 = _parse_ymd(from_s)
    d2 = _parse_ymd(to_s)
    if not d1 or not d2:
        return (None, None)

    if d1 > d2:
        d1, d2 = d2, d1

    tz = timezone.get_current_timezone()
    start_dt = timezone.make_aware(datetime.combine(d1, time.min), tz)
    end_dt = timezone.make_aware(datetime.combine(d2, time.max), tz)

    start_ms = int(start_dt.timestamp() * 1000)
    end_ms = int(end_dt.timestamp() * 1000)
    return (start_ms, end_ms)


def _filter_table_by_range_ms(table, start_ms, end_ms):
    if not start_ms or not end_ms:
        return table

    out = []
    for item in (table or []):
        ad = (item or {}).get("anomaly_data") or {}
        t = ad.get("time")
        try:
            t_ms = int(str(t).strip())
        except Exception:
            continue

        if start_ms <= t_ms <= end_ms:
            out.append(item)

    return out


def _api_period_for_site24x7(period_ui: int) -> int:
    return period_ui if period_ui in (2, 3, 5) else 3


# =========================
# Views
# =========================
@tenant_required
@login_required
def monitor_status(request):
    tenant = _resolve_tenant(request)
    tenants_list = _tenants_list_for_user(request.user)
    selected_paises = _selected_paises_for_tenant(tenant)

    if tenant is None:
        return render(request, "site24x7/monitor_status.html", {
            "tenant": None,
            "all_tenants": tenants_list,
            "error": False,
            "customer_name": "",
            "monitors": [],
            "zaaid": "",
            "total_monitors": 0,
            "count_down": 0,
            "count_up": 0,
            "count_trouble": 0,
            "count_critical": 0,
            "count_suspended": 0,
            "whitelist_countries": ALL_COUNTRIES,
            "selected_paises": selected_paises,
        })

    zaaid = getattr(tenant, "site24x7_id", "")
    if not zaaid:
        return render(request, "site24x7/monitor_status.html", {
            "tenant": tenant,
            "all_tenants": tenants_list,
            "error": False,
            "customer_name": "",
            "monitors": [],
            "zaaid": "",
            "total_monitors": 0,
            "count_down": 0,
            "count_up": 0,
            "count_trouble": 0,
            "count_critical": 0,
            "count_suspended": 0,
            "whitelist_countries": ALL_COUNTRIES,
            "selected_paises": selected_paises,
        })

    try:
        access_token = get_site24x7_token()
        customer = fetch_customer_status(access_token, zaaid)
    except Exception as e:
        logger.exception("[SITE24X7] Error al consultar Site24x7: %s", e)
        return render(request, "site24x7/monitor_status.html", {
            "tenant": tenant,
            "all_tenants": tenants_list,
            "error": True,
            "customer_name": "",
            "monitors": [],
            "zaaid": zaaid or "",
            "total_monitors": 0,
            "count_down": 0,
            "count_up": 0,
            "count_trouble": 0,
            "count_critical": 0,
            "count_suspended": 0,
            "whitelist_countries": ALL_COUNTRIES,
            "selected_paises": selected_paises,
        })

    raw_monitors = customer.get("monitors", []) or []
    monitors: List[Dict[str, Any]] = []
    for m in raw_monitors:
        m_copy = dict(m)
        m_copy["last_polled_human"] = format_last_polled(m_copy.get("last_polled_time"))
        monitors.append(m_copy)

    counters = build_counters(monitors)

    return render(request, "site24x7/monitor_status.html", {
        "tenant": tenant,
        "all_tenants": tenants_list,
        "error": False,
        "customer_name": customer.get("customer_name", ""),
        "zaaid": customer.get("zaaid", zaaid),
        "monitors": monitors,
        "total_monitors": len(monitors),
        "count_down": counters["down"],
        "count_up": counters["up"],
        "count_trouble": counters["trouble"],
        "count_critical": counters["critical"],
        "count_suspended": counters["suspended"],
        "whitelist_countries": ALL_COUNTRIES,
        "selected_paises": selected_paises,
    })


def summarize_anomaly_info(anomaly_info: dict) -> dict:
    if not isinstance(anomaly_info, dict):
        return {
            "total_count": 0,
            "top_severity": "—",
            "breakdown": {"info": 0, "likely": 0, "confirmed": 0},
        }

    def norm_sev(label: str) -> str:
        s = (label or "").strip().lower()
        if s.startswith("info") or s.startswith("información"):
            return "info"
        if s.startswith("probable") or s.startswith("likely"):
            return "likely"
        if s.startswith("confirm"):
            return "confirmed"
        return "other"

    sev_rank = {"info": 1, "likely": 2, "confirmed": 3}

    total = 0
    breakdown = {"info": 0, "likely": 0, "confirmed": 0}
    top_label_original = "—"
    top_rank = 0

    for _, sev_block in anomaly_info.items():
        if not isinstance(sev_block, dict):
            continue

        try:
            count = int(sev_block.get("anomaly_count") or 0)
        except (TypeError, ValueError):
            count = 0

        label = sev_block.get("severity") or ""
        norm = norm_sev(label)

        total += count
        if norm in breakdown:
            breakdown[norm] += count

        rank = sev_rank.get(norm, 0)
        if rank > top_rank and count > 0:
            top_rank = rank
            top_label_original = label or "—"

    if total == 0:
        top_label_original = "—"

    return {
        "total_count": total,
        "top_severity": top_label_original,
        "breakdown": breakdown,
    }


@tenant_required
@login_required
def anomaly_status(request):
    tenant = _resolve_tenant(request)
    tenants_list = _tenants_list_for_user(request.user)
    selected_paises = _selected_paises_for_tenant(tenant)

    period_ui = _get_period_from_request(request, default=3)
    start_ms, end_ms = _get_custom_range_ms_from_request(request, period=period_ui)

    from_s = (request.GET.get("from") or "").strip() if period_ui == 50 else ""
    to_s = (request.GET.get("to") or "").strip() if period_ui == 50 else ""

    period_label_map = {
        3: "Hoy",
        2: "Últimos 7 días",
        5: "Últimos 30 días",
        50: "Personalizado",
    }
    period_label = period_label_map.get(period_ui, "—")

    base_context = {
        "all_tenants": tenants_list,
        "whitelist_countries": ALL_COUNTRIES,
        "selected_paises": selected_paises,
        "period": period_ui,
        "from_date": from_s,
        "to_date": to_s,
        "period_label": period_label,
    }

    if tenant is None:
        return render(request, "site24x7/anomaly_status.html", {
            **base_context,
            "tenant": None,
            "error": False,
            "monitors": [],
            "total_monitors": 0,
            "total_anomalies": 0,
            "count_info": 0,
            "count_likely": 0,
            "count_confirmed": 0,
        })

    zaaid = getattr(tenant, "site24x7_id", "")
    if not zaaid:
        return render(request, "site24x7/anomaly_status.html", {
            **base_context,
            "tenant": tenant,
            "error": False,
            "monitors": [],
            "total_monitors": 0,
            "total_anomalies": 0,
            "count_info": 0,
            "count_likely": 0,
            "count_confirmed": 0,
        })

    api_period = _api_period_for_site24x7(period_ui)

    try:
        access_token = get_site24x7_token()
        summary = fetch_anomaly_summary(
            access_token,
            zaaid=zaaid,
            period=api_period,
            monitor_type=None,
            start_ms=start_ms,
            end_ms=end_ms,
        )
    except Exception as e:
        logger.exception("[SITE24X7] Error al consultar anomalías Site24x7: %s", e)
        return render(request, "site24x7/anomaly_status.html", {
            **base_context,
            "tenant": tenant,
            "error": True,
            "monitors": [],
            "total_monitors": 0,
            "total_anomalies": 0,
            "count_info": 0,
            "count_likely": 0,
            "count_confirmed": 0,
        })

    raw_monitors = (summary or {}).get("monitors", []) or []

    monitors = []
    total_anomalies = 0
    count_info = 0
    count_likely = 0
    count_confirmed = 0

    for m in raw_monitors:
        info = m.get("anomaly_info") or {}
        summary_info = summarize_anomaly_info(info)

        monitor_total = summary_info["total_count"]
        total_anomalies += monitor_total

        breakdown = summary_info["breakdown"]
        count_info += breakdown.get("info", 0)
        count_likely += breakdown.get("likely", 0)
        count_confirmed += breakdown.get("confirmed", 0)

        monitors.append({
            "monitor_id": m.get("monitor_id"),
            "display_name": m.get("display_name"),
            "anomaly_count": monitor_total,
            "severity": summary_info["top_severity"],
        })

    return render(request, "site24x7/anomaly_status.html", {
        **base_context,
        "tenant": tenant,
        "error": False,
        "monitors": monitors,
        "total_monitors": len(monitors),
        "total_anomalies": total_anomalies,
        "count_info": count_info,
        "count_likely": count_likely,
        "count_confirmed": count_confirmed,
    })


def _format_epoch_ms_to_local(value):
    if not value:
        return "—"
    try:
        ms = int(str(value).strip())
        dt = datetime.fromtimestamp(ms / 1000.0, tz=timezone.get_current_timezone())
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return str(value)


@tenant_required
@login_required
def anomaly_list(request):
    tenant = _resolve_tenant(request)

    monitor_id = request.GET.get("monitor_id")
    monitor_name = request.GET.get("monitor_name", "")

    zaaid = str(getattr(tenant, "site24x7_id", "") or "")
    if not monitor_id or not tenant or not zaaid:
        return render(request, "site24x7/anomaly_list.html", {
            "error": True,
            "monitor_name": monitor_name,
            "anomalies": [],
        })

    period_ui = _get_period_from_request(request, default=3)
    start_ms, end_ms = _get_custom_range_ms_from_request(request, period=period_ui)
    api_period = _api_period_for_site24x7(period_ui)

    try:
        access_token = get_site24x7_token()
        data = fetch_anomaly_by_monitor(
            access_token=access_token,
            zaaid=zaaid,
            monitor_id=monitor_id,
            period=api_period,
            severity="CONFIRMED,LIKELY,INFO",
            start_ms=start_ms,
            end_ms=end_ms,
        )
    except Exception as e:
        logger.exception("[SITE24X7] Error al consultar listado de anomalías: %s", e)
        return render(request, "site24x7/anomaly_list.html", {
            "error": True,
            "monitor_name": monitor_name,
            "anomalies": [],
        })

    table = data.get("anomaly_table_data", []) or []
    if period_ui == 50 and start_ms and end_ms:
        table = _filter_table_by_range_ms(table, start_ms, end_ms)

    anomalies = []
    for idx, item in enumerate(table):
        ad = item.get("anomaly_data") or {}

        raw_comments = ad.get("comment") or []
        flat_comments = []

        for entry in raw_comments:
            if isinstance(entry, dict) and "location_comments" in entry:
                loc_name = entry.get("location_name")
                for lc in entry.get("location_comments") or []:
                    if not isinstance(lc, dict):
                        continue
                    c = dict(lc)
                    c["location_name"] = loc_name
                    c["display_attr"] = (
                        c.get("formatted_attribute")
                        or c.get("attribute_name")
                        or "Atributo"
                    )
                    flat_comments.append(c)

            elif isinstance(entry, list):
                for lc in entry:
                    if not isinstance(lc, dict):
                        continue
                    c = dict(lc)
                    c["display_attr"] = (
                        c.get("formatted_attribute")
                        or c.get("attribute_name")
                        or "Atributo"
                    )
                    flat_comments.append(c)

            elif isinstance(entry, dict):
                c = dict(entry)
                c["display_attr"] = (
                    c.get("formatted_attribute")
                    or c.get("attribute_name")
                    or "Atributo"
                )
                flat_comments.append(c)

        anomalies.append({
            "idx": idx,
            "display_name": item.get("display_name") or monitor_name or "—",
            "monitor_type": ad.get("monitor_type") or "—",
            "severity": ad.get("severity") or "—",
            "time_raw": ad.get("time"),
            "time_human": _format_epoch_ms_to_local(ad.get("time")),
            "comments": flat_comments,
        })

    return render(request, "site24x7/anomaly_list.html", {
        "error": False,
        "monitor_name": monitor_name,
        "anomalies": anomalies,
    })


@tenant_required
@login_required
def anomaly_detail(request):
    tenant = _resolve_tenant(request)

    monitor_id = request.GET.get("monitor_id")
    monitor_name = request.GET.get("monitor_name", "")

    zaaid = str(getattr(tenant, "site24x7_id", "") or "")
    if not monitor_id or not tenant or not zaaid:
        return render(request, "site24x7/anomaly_detail.html", {
            "error": True,
            "monitor_name": monitor_name,
            "rows": [],
        })

    period_ui = _get_period_from_request(request, default=3)
    start_ms, end_ms = _get_custom_range_ms_from_request(request, period=period_ui)
    api_period = _api_period_for_site24x7(period_ui)

    try:
        access_token = get_site24x7_token()
        data = fetch_anomaly_by_monitor(
            access_token=access_token,
            zaaid=zaaid,
            monitor_id=monitor_id,
            period=api_period,
            severity="CONFIRMED,LIKELY,INFO",
            start_ms=start_ms,
            end_ms=end_ms,
        )
    except Exception as e:
        logger.exception("[SITE24X7] Error al consultar detalle de anomalías: %s", e)
        return render(request, "site24x7/anomaly_detail.html", {
            "error": True,
            "monitor_name": monitor_name,
            "rows": [],
        })

    table = data.get("anomaly_table_data", []) or []
    if period_ui == 50 and start_ms and end_ms:
        table = _filter_table_by_range_ms(table, start_ms, end_ms)

    rows = []
    for item in table:
        ad = item.get("anomaly_data") or {}

        raw_comments = ad.get("comment") or []
        flat_comments = []

        for entry in raw_comments:
            if isinstance(entry, dict) and "location_comments" in entry:
                loc_name = entry.get("location_name")
                for lc in entry.get("location_comments") or []:
                    if not isinstance(lc, dict):
                        continue
                    c = dict(lc)
                    c["location_name"] = loc_name
                    c["display_attr"] = (
                        c.get("formatted_attribute")
                        or c.get("attribute_name")
                        or "Atributo"
                    )
                    flat_comments.append(c)

            elif isinstance(entry, list):
                for lc in entry:
                    if not isinstance(lc, dict):
                        continue
                    c = dict(lc)
                    c["display_attr"] = (
                        c.get("formatted_attribute")
                        or c.get("attribute_name")
                        or "Atributo"
                    )
                    flat_comments.append(c)

            elif isinstance(entry, dict):
                c = dict(entry)
                c["display_attr"] = (
                    c.get("formatted_attribute")
                    or c.get("attribute_name")
                    or "Atributo"
                )
                flat_comments.append(c)

        rows.append({
            "display_name": item.get("display_name") or monitor_name or "—",
            "time": ad.get("time"),
            "severity": ad.get("severity"),
            "monitor_type": ad.get("monitor_type"),
            "comments": flat_comments,
        })

    return render(request, "site24x7/anomaly_detail.html", {
        "error": False,
        "monitor_name": monitor_name,
        "rows": rows,
    })


@tenant_required
@login_required
def dashboard(request):
    tenant = getattr(request, "tenant", None)

    if tenant is None:
        tenant_id = request.session.get("tenant_id")
        if tenant_id:
            tenant = Tenant.objects.filter(id=tenant_id).first()

    if tenant is None:
        tenant = getattr(request.user, "tenant", None)

    tenants_list = _tenants_list_for_user(request.user)
    selected_paises = _selected_paises_for_tenant(tenant)

    if tenant is None:
        return render(request, "site24x7/dashboard.html", {
            "tenant": None,
            "all_tenants": tenants_list,
            "iframe_url": None,
            "whitelist_countries": ALL_COUNTRIES,
            "selected_paises": selected_paises,
        })

    iframe_url = None
    try:
        embed = tenant.dashboard_iframe
        iframe_url = embed.iframe_url
    except TenantDashboardEmbed.DoesNotExist:
        iframe_url = None
    except TenantDashboardEmbed.MultipleObjectsReturned:
        embed = TenantDashboardEmbed.objects.filter(tenant=tenant).first()
        iframe_url = embed.iframe_url if embed else None

    return render(request, "site24x7/dashboard.html", {
        "tenant": tenant,
        "all_tenants": tenants_list,
        "iframe_url": iframe_url,
        "whitelist_countries": ALL_COUNTRIES,
        "selected_paises": selected_paises,
    })
