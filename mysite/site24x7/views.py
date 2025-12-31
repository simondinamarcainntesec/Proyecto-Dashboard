# site24x7/views.py
import json
import os
import ssl
import urllib.request
from pathlib import Path
from typing import Any, List, Dict, Tuple
from datetime import datetime, time

import requests
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils import timezone

from tenants.decorators import tenant_required
from tenants.models import Tenant, TenantUser, TenantDashboardEmbed
from .services import (
    fetch_anomaly_summary,
    fetch_anomaly_by_monitor,
)

# Preferencias de países (POR TENANT)
from home.models import WhitelistCountryPreference, TenantCredentials  # añadido
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
    Lee la preferencia desde WhitelistCountryPreference.tenant (NO existe field user).
    """
    try:
        if not tenant:
            return []
        pref = WhitelistCountryPreference.objects.filter(tenant=tenant).first()
        return (pref.paises or []) if pref else []
    except Exception as e:
        logger.exception("[SITE24X7] Error leyendo preferencias de países (tenant): %s", e)
        return []


def _active_cred_for_tenant(tenant):
    """
    Credenciales desde agent.tenant_credentials (TenantCredentials).
    Retorna None si no hay credenciales activas.
    """
    try:
        if not tenant:
            return None
        return TenantCredentials.get_active_for_tenant(int(tenant.id))
    except Exception as e:
        logger.exception(
            "[SITE24X7] Error leyendo TenantCredentials tenant_id=%s: %s",
            getattr(tenant, "id", None),
            e
        )
        return None


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
# Date filter helpers (UI)
# =========================
def _parse_ymd(s: str):
    s = (s or "").strip()
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
        return None


def _get_period_from_request(request, default=3) -> int:
    """
    Lee period desde querystring.
    - Si viene duplicado (period=5&period=3), usa el ÚLTIMO válido.
    """
    periods = [p.strip() for p in request.GET.getlist("period") if (p or "").strip()]

    for p in reversed(periods):
        try:
            pi = int(p)
        except Exception:
            continue
        if pi in (2, 3, 5):
            return pi

    try:
        default_i = int(default)
    except Exception:
        default_i = 3

    return default_i if default_i in (2, 3, 5) else 3



# =========================
# Anomaly period resolution (FIX REAL)
# - NO usa start_time/end_time (tu API devuelve 1107)
# - Descubre automáticamente qué "period" real corresponde a 7/30 días para ESTE tenant
# =========================
# =========================
# Anomaly period resolution (FIX DEFINITIVO)
# - NO adivina periodos (evita swap 7<->30)
# - Mantiene solo detección opcional de "merge hoy" (si el rango viene till yesterday)
# =========================
_ANOM_PERIOD_CACHE: Dict[str, dict] = {}
_ANOM_PERIOD_CACHE_TTL_SECONDS = 1  # 5 min


def _score_anomaly_summary(summary: dict) -> int:
    """
    Puntaje simple: total de anomalías sumadas en todos los monitores.
    """
    try:
        monitors = (summary or {}).get("monitors", []) or []
    except Exception:
        monitors = []

    total = 0
    for m in monitors:
        info = (m or {}).get("anomaly_info") or {}
        if not isinstance(info, dict):
            continue
        for _, sev_block in info.items():
            if not isinstance(sev_block, dict):
                continue
            try:
                total += int(sev_block.get("anomaly_count") or 0)
            except Exception:
                continue
    return int(total)


def _fetch_summary_safe(access_token: str, zaaid: str, period: int) -> dict:
    try:
        return fetch_anomaly_summary(access_token, zaaid=zaaid, period=int(period), monitor_type=None)
    except Exception:
        return {}


def _resolve_anomaly_periods(access_token: str, zaaid: str) -> dict:
    """
    Mapeo OFICIAL (estable):
      - HOY: period=3
      - Últimos 7 días: period=2
      - Últimos 30 días: period=5

    Además detecta si el rango parece excluir HOY (till yesterday):
      - merge7/merge30 = True si score_rango < score_hoy (y score_hoy > 0)
    """
    key = str(zaaid or "").strip()
    if not key:
        return {
            "ts": 0,
            "today": 3,
            "p7": 2,
            "p30": 5,
            "merge7": False,
            "merge30": False,
            "score_today": 0,
            "score_p7": 0,
            "score_p30": 0,
        }

    now_ts = int(timezone.now().timestamp())
    cached = _ANOM_PERIOD_CACHE.get(key)
    if cached and (now_ts - int(cached.get("ts") or 0) <= _ANOM_PERIOD_CACHE_TTL_SECONDS):
        return cached

    # Fijo (NO adivinar)
    today_p = 3
    p7 = 2
    p30 = 5

    s_today = _fetch_summary_safe(access_token, key, today_p)
    s_7 = _fetch_summary_safe(access_token, key, p7)
    s_30 = _fetch_summary_safe(access_token, key, p30)

    score_today = _score_anomaly_summary(s_today)
    score_7 = _score_anomaly_summary(s_7)
    score_30 = _score_anomaly_summary(s_30)

    # Si el rango NO incluye hoy, su score podría quedar < score_today.
    # (evita merge si hoy es 0)
    merge7 = bool(score_today > 0 and score_7 < score_today)
    merge30 = bool(score_today > 0 and score_30 < score_today)

    resolved = {
        "ts": now_ts,
        "today": today_p,
        "p7": p7,
        "p30": p30,
        "merge7": merge7,
        "merge30": merge30,
        "score_today": int(score_today),
        "score_p7": int(score_7),
        "score_p30": int(score_30),
    }
    _ANOM_PERIOD_CACHE[key] = resolved
    return resolved



def _merge_monitor_summaries(summary_a: dict, summary_b: dict) -> dict:
    """
    Une dos summaries tipo /reports/anomaly, sumando conteos por monitor_id.
    (Usado SOLO cuando inferimos que el rango excluye hoy.)
    """
    out = {"monitors": []}

    def add_block(dst: dict, src: dict):
        for sev_key, sev_block in (src or {}).items():
            if not isinstance(sev_block, dict):
                continue
            k = sev_key
            if k not in dst or not isinstance(dst.get(k), dict):
                dst[k] = dict(sev_block)
                try:
                    dst[k]["anomaly_count"] = int(dst[k].get("anomaly_count") or 0)
                except Exception:
                    dst[k]["anomaly_count"] = 0
            else:
                try:
                    dst[k]["anomaly_count"] = int(dst[k].get("anomaly_count") or 0) + int(sev_block.get("anomaly_count") or 0)
                except Exception:
                    pass
                if not dst[k].get("severity") and sev_block.get("severity"):
                    dst[k]["severity"] = sev_block.get("severity")

    by_id: Dict[str, dict] = {}

    for src in [summary_a or {}, summary_b or {}]:
        for m in (src.get("monitors") or []):
            mid = str(m.get("monitor_id") or "")
            if not mid:
                continue
            if mid not in by_id:
                by_id[mid] = {
                    "monitor_id": m.get("monitor_id"),
                    "display_name": m.get("display_name"),
                    "anomaly_info": {},
                }
            if not by_id[mid].get("display_name") and m.get("display_name"):
                by_id[mid]["display_name"] = m.get("display_name")

            add_block(by_id[mid]["anomaly_info"], m.get("anomaly_info") or {})

    out["monitors"] = list(by_id.values())
    return out


def _merge_anomaly_tables(table_a: list, table_b: list) -> list:
    """
    Une anomaly_table_data evitando duplicados. Ordena desc por time (ms) al final.
    """
    seen = set()
    out = []

    def key_for(item: dict):
        ad = (item or {}).get("anomaly_data") or {}
        t = str(ad.get("time") or "")
        sev = str(ad.get("severity") or "")
        mtype = str(ad.get("monitor_type") or "")
        name = str(item.get("display_name") or item.get("monitor_name") or item.get("monitor_display_name") or "")
        return f"{t}|{sev}|{mtype}|{name}"

    for src in (table_a or []):
        k = key_for(src)
        if k in seen:
            continue
        seen.add(k)
        out.append(src)

    for src in (table_b or []):
        k = key_for(src)
        if k in seen:
            continue
        seen.add(k)
        out.append(src)

    def t_ms(item):
        ad = (item or {}).get("anomaly_data") or {}
        try:
            return int(str(ad.get("time") or "0").strip())
        except Exception:
            return 0

    out.sort(key=t_ms, reverse=True)
    return out


# =========================
# Views
# =========================
@tenant_required
@login_required
def monitor_status(request):
    tenant = _resolve_tenant(request)
    tenants_list = _tenants_list_for_user(request.user)
    selected_paises = _selected_paises_for_tenant(tenant)
    cred = _active_cred_for_tenant(tenant)  # añadido

    if tenant is None:
        return render(request, "site24x7/monitor_status.html", {
            "tenant": None,
            "all_tenants": tenants_list,
            "cred": cred,  # añadido
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
            "cred": cred,  # añadido
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
            "cred": cred,  # añadido
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
        "cred": cred,  # añadido
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
    cred = _active_cred_for_tenant(tenant)  # añadido

    period_ui = _get_period_from_request(request, default=3)

    period_label_map = {
        3: "Hoy",
        2: "Últimos 7 días",
        5: "Últimos 30 días",
    }
    period_label = period_label_map.get(period_ui, "—")

    base_context = {
        "all_tenants": tenants_list,
        "whitelist_countries": ALL_COUNTRIES,
        "selected_paises": selected_paises,
        "period": period_ui,
        "from_date": "",
        "to_date": "",
        "period_label": period_label,
        "cred": cred,  # añadido
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

    try:
        access_token = get_site24x7_token()

        # Resolver periods reales por tenant
        periods = _resolve_anomaly_periods(access_token, str(zaaid))
        logger.info(
        "[ANOM] zaaid=%s UI=%s -> today=%s p7=%s p30=%s merge7=%s merge30=%s scores(t=%s,7=%s,30=%s)",
        zaaid, period_ui,
        periods.get("today"), periods.get("p7"), periods.get("p30"),
        periods.get("merge7"), periods.get("merge30"),
        periods.get("score_today"), periods.get("score_p7"), periods.get("score_p30")
    )


        if period_ui == 3:
            summary = fetch_anomaly_summary(access_token, zaaid=str(zaaid), period=periods["today"], monitor_type=None)
        elif period_ui == 2:
            summary_range = fetch_anomaly_summary(access_token, zaaid=str(zaaid), period=int(periods["p7"]), monitor_type=None)
            if periods.get("merge7"):
                summary_today = fetch_anomaly_summary(access_token, zaaid=str(zaaid), period=periods["today"], monitor_type=None)
                summary = _merge_monitor_summaries(summary_range, summary_today)
            else:
                summary = summary_range
        else:  # period_ui == 5
            summary_range = fetch_anomaly_summary(access_token, zaaid=str(zaaid), period=int(periods["p30"]), monitor_type=None)
            if periods.get("merge30"):
                summary_today = fetch_anomaly_summary(access_token, zaaid=str(zaaid), period=periods["today"], monitor_type=None)
                summary = _merge_monitor_summaries(summary_range, summary_today)
            else:
                summary = summary_range

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

    try:
        access_token = get_site24x7_token()
        periods = _resolve_anomaly_periods(access_token, zaaid)

        if period_ui == 3:
            api_period = periods["today"]
            merge_today = False
        elif period_ui == 2:
            api_period = int(periods["p7"])
            merge_today = bool(periods.get("merge7"))
        else:
            api_period = int(periods["p30"])
            merge_today = bool(periods.get("merge30"))

        # NO enviar start_time/end_time (tu API devuelve 1107)
        data_range = fetch_anomaly_by_monitor(
            access_token=access_token,
            zaaid=zaaid,
            monitor_id=monitor_id,
            period=int(api_period),
            severity="CONFIRMED,LIKELY,INFO",
            start_ms=None,
            end_ms=None,
        )

        data_today = None
        if merge_today:
            data_today = fetch_anomaly_by_monitor(
                access_token=access_token,
                zaaid=zaaid,
                monitor_id=monitor_id,
                period=int(periods["today"]),
                severity="CONFIRMED,LIKELY,INFO",
                start_ms=None,
                end_ms=None,
            )

    except Exception as e:
        logger.exception("[SITE24X7] Error al consultar listado de anomalías: %s", e)
        return render(request, "site24x7/anomaly_list.html", {
            "error": True,
            "monitor_name": monitor_name,
            "anomalies": [],
        })

    table = (data_range or {}).get("anomaly_table_data", []) or []
    if data_today:
        table_today = (data_today or {}).get("anomaly_table_data", []) or []
        table = _merge_anomaly_tables(table, table_today)

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

    try:
        access_token = get_site24x7_token()
        periods = _resolve_anomaly_periods(access_token, zaaid)

        if period_ui == 3:
            api_period = periods["today"]
            merge_today = False
        elif period_ui == 2:
            api_period = int(periods["p7"])
            merge_today = bool(periods.get("merge7"))
        else:
            api_period = int(periods["p30"])
            merge_today = bool(periods.get("merge30"))

        data_range = fetch_anomaly_by_monitor(
            access_token=access_token,
            zaaid=zaaid,
            monitor_id=monitor_id,
            period=int(api_period),
            severity="CONFIRMED,LIKELY,INFO",
            start_ms=None,
            end_ms=None,
        )

        data_today = None
        if merge_today:
            data_today = fetch_anomaly_by_monitor(
                access_token=access_token,
                zaaid=zaaid,
                monitor_id=monitor_id,
                period=int(periods["today"]),
                severity="CONFIRMED,LIKELY,INFO",
                start_ms=None,
                end_ms=None,
            )

    except Exception as e:
        logger.exception("[SITE24X7] Error al consultar detalle de anomalías: %s", e)
        return render(request, "site24x7/anomaly_detail.html", {
            "error": True,
            "monitor_name": monitor_name,
            "rows": [],
        })

    table = (data_range or {}).get("anomaly_table_data", []) or []
    if data_today:
        table_today = (data_today or {}).get("anomaly_table_data", []) or []
        table = _merge_anomaly_tables(table, table_today)

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
    cred = _active_cred_for_tenant(tenant)  # añadido

    if tenant is None:
        return render(request, "site24x7/dashboard.html", {
            "tenant": None,
            "all_tenants": tenants_list,
            "cred": cred,  # añadido
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
        "cred": cred,  # añadido
        "iframe_url": iframe_url,
        "whitelist_countries": ALL_COUNTRIES,
        "selected_paises": selected_paises,
    })
