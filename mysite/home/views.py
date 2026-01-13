# home/views.py
from __future__ import annotations

from datetime import datetime, timezone as dt_timezone, timedelta
import logging
import os
import base64
from urllib.parse import urlencode

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.db.models import F, Value, TextField, Q, Count
from django.db.models.functions import Lower, Replace, Trim, Cast, TruncDate
from django.db import transaction
import json

from tenants.decorators import tenant_required
from tenants.models import Tenant, TenantUser, NotificationChannelPreference, Tenants_contracts
from tenants.views import normalize_e164_phone

from inyeccion_api.models import Alarm
from soar_incidents.models import IncidenteSOAR
from .models import (
    TelegramSolicitud,
    IPBlacklist,
    IPWhitelist,
    TenantCredentials,
    WhitelistCountryPreference,
)
from .countries import ALL_COUNTRIES, COUNTRY_BY_CODE
from dashboard.charts import make_base_qs
import requests
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.utils import timezone as dj_timezone
from django.contrib import messages
from django.urls import reverse
from django.views.decorators.http import require_POST, require_GET, require_http_methods

logger = logging.getLogger(__name__)


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


def _annotate_norm_field(qs, field_name: str, alias: str):
    cleaned = Cast(F(field_name), TextField())
    for ch in ["{", "}", "[", "]", '"', "'", " "]:
        cleaned = Replace(cleaned, Value(ch), Value(""), output_field=TextField())
    cleaned = Trim(cleaned, output_field=TextField())
    cleaned = Lower(cleaned, output_field=TextField())
    return qs.annotate(**{alias: cleaned})


# ──────────────────────────────────────────────────────────────────────────────
# Normalización y lógica de severidad (msg_severity + severity)
# ──────────────────────────────────────────────────────────────────────────────

CRITICAL_TERMS = ["critical", "critico", "crítica", "critica"]
HIGH_TERMS = ["high", "alto"]
MEDIUM_TERMS = ["medium", "medio", "media"]
LOW_TERMS = ["low", "bajo"]
INFO_TERMS = ["info", "informational", "informacion", "información"]

KNOWN_SEVERITY_TERMS = (
    CRITICAL_TERMS
    + HIGH_TERMS
    + MEDIUM_TERMS
    + LOW_TERMS
    + INFO_TERMS
)


def _annotate_severity_fields(qs):
    """
    Anota:
      - msg_severity -> msg_sev_norm
      - severity     -> sev_norm
    usando la misma limpieza que el resto del proyecto.
    """
    qs = _annotate_norm_field(qs, "msg_severity", "msg_sev_norm")
    qs = _annotate_norm_field(qs, "severity", "sev_norm")
    return qs


CRITICAL_FILTER = (
    Q(msg_sev_norm__in=CRITICAL_TERMS)
    | (
        ~Q(msg_sev_norm__in=KNOWN_SEVERITY_TERMS)
        & Q(sev_norm__in=CRITICAL_TERMS)
    )
)


def _get_user_telegram_id(user) -> str | None:
    val = getattr(user, "telegram_id", None)
    if val:
        return str(val).strip()
    try:
        tu = getattr(user, "tenantuser", None)
        if tu and getattr(tu, "telegram_id", None):
            return str(tu.telegram_id).strip()
    except Exception:
        pass
    try:
        tu = TenantUser.objects.filter(user=user).order_by("-id").first()
        if tu and getattr(tu, "telegram_id", None):
            return str(tu.telegram_id).strip()
    except Exception:
        pass
    return None


def _split_search_terms(raw: str) -> list[str]:
    if not raw:
        return []
    return [part.strip() for part in raw.split(",") if part.strip()]


def _parse_country_codes(raw: str) -> list[str]:
    """
    Convierte 'CL, AR, US' -> ['CL', 'AR', 'US'] (en mayúsculas, sin espacios vacíos).
    """
    if not raw:
        return []
    return [c.strip().upper() for c in raw.split(",") if c.strip()]


def _ensure_list_of_str(val) -> list[str]:
    """
    Normaliza cualquier cosa a list[str].
    - None -> []
    - 'CL,AR' -> ['CL,AR'] (no parsea, solo normaliza tipo)
    - tuple/set -> list(...)
    - list -> filtra None y castea a str
    """
    if val is None:
        return []
    if isinstance(val, list):
        out = []
        for x in val:
            if x is None:
                continue
            sx = str(x).strip()
            if sx:
                out.append(sx)
        return out
    if isinstance(val, (tuple, set)):
        out = []
        for x in list(val):
            if x is None:
                continue
            sx = str(x).strip()
            if sx:
                out.append(sx)
        return out
    # cualquier otro tipo: lo metemos como un solo item string
    s = str(val).strip()
    return [s] if s else []


def _save_country_pref(tenant, paises: list[str]) -> None:
    """
    Guarda en agent.whitelist_country_preference la lista de países (NOMBRES)
    seleccionados POR TENANT (UN REGISTRO POR TENANT).
    """
    from django.utils import timezone as _tz

    if not tenant:
        raise ValueError("Tenant requerido para guardar preferencia de países.")

    WhitelistCountryPreference.objects.update_or_create(
        tenant=tenant,
        defaults={
            "paises": _ensure_list_of_str(paises),
            "updated_at": _tz.now(),
        },
    )


# ──────────────────────────────────────────────────────────────────────────────
# Helper: IP del cliente
# ──────────────────────────────────────────────────────────────────────────────
def _get_client_ip(request) -> str:
    xff = (request.META.get("HTTP_X_FORWARDED_FOR") or "").strip()
    if xff:
        return xff.split(",")[0].strip()
    return (request.META.get("REMOTE_ADDR") or "").strip()


# ──────────────────────────────────────────────────────────────────────────────
# Upsert a agent.ip_whitelist al descargar
# ──────────────────────────────────────────────────────────────────────────────
def _upsert_whitelist_from_download(
    request,
    creds: TenantCredentials | None = None,
) -> None:
    try:
        logger.info(
            "[WHITELIST UPSERT] Iniciando upsert. creds_pk=%s",
            getattr(creds, "pk", None),
        )

        ip = _get_client_ip(request)
        logger.info("[WHITELIST UPSERT] IP detectada: %s", ip)

        if not ip:
            logger.warning("[WHITELIST UPSERT] No se pudo obtener IP del request, abortando.")
            return

        user = getattr(request, "user", None)
        logger.info(
            "[WHITELIST UPSERT] Usuario en request: %s",
            getattr(user, "username", None),
        )

        tenant_obj = None
        if creds is not None:
            tenant_obj = getattr(creds, "tenant", None)
            logger.info(
                "[WHITELIST UPSERT] Tenant desde creds.tenant: %s",
                getattr(tenant_obj, "name", None),
            )

        if tenant_obj is None:
            tenant_from_request = getattr(request, "tenant", None)
            tenant_from_user = getattr(user, "tenant", None)
            logger.info(
                "[WHITELIST UPSERT] Tenant desde request.tenant: %s | user.tenant: %s",
                getattr(tenant_from_request, "name", None),
                getattr(tenant_from_user, "name", None),
            )
            tenant_obj = tenant_from_request or tenant_from_user

        tenant_name = (getattr(tenant_obj, "name", "") or "").strip() if tenant_obj else ""
        tenant_id = getattr(tenant_obj, "id", None) if tenant_obj else None

        cred_tenant_id = getattr(creds, "tenant_id", None) if creds else None
        cred_tenant_name = (getattr(creds, "tenant_name", "") or "").strip() if creds else ""

        if not tenant_id and cred_tenant_id:
            tenant_id = cred_tenant_id

        if not tenant_name and cred_tenant_name:
            tenant_name = cred_tenant_name

        logger.info(
            "[WHITELIST UPSERT] Tenant resuelto: name='%s', id=%s (cred_name='%s', cred_id=%s)",
            tenant_name,
            tenant_id,
            cred_tenant_name,
            cred_tenant_id,
        )

        if not tenant_name:
            tenant_name = "Tenant desconocido"

        now = dj_timezone.now()

        logger.info(
            "[WHITELIST UPSERT] Antes de get_or_create: ip=%s, cliente='%s', tenant_id=%s",
            ip,
            tenant_name,
            tenant_id,
        )

        obj, created = IPWhitelist.objects.get_or_create(
            ip=ip,
            defaults={
                "cliente": tenant_name,
                "organizacion": tenant_name,
                "fecha_creacion": now,
                "fecha_actualizacion": now,
                "motivo": "Automatizado",
                "tenant_id": tenant_id,
            },
        )

        logger.info(
            "[WHITELIST UPSERT] get_or_create ejecutado. created=%s, obj_pk=%s",
            created,
            getattr(obj, "pk", None),
        )

        if not created:
            update_kwargs = {
                "fecha_actualizacion": now,
                "cliente": tenant_name,
                "organizacion": tenant_name,
            }
            if tenant_id is not None:
                update_kwargs["tenant_id"] = tenant_id

            logger.info(
                "[WHITELIST UPSERT] Actualizando registro existente pk=%s con %s",
                obj.pk,
                update_kwargs,
            )
            IPWhitelist.objects.filter(pk=obj.pk).update(**update_kwargs)

        logger.info(
            "[WHITELIST UPSERT] Finalizado OK para ip=%s, cliente='%s', tenant_id=%s",
            ip,
            tenant_name,
            tenant_id,
        )

    except Exception:
        logger.exception("[WHITELIST UPSERT] Error inesperado durante el upsert")


def _build_severity_summary(qs):
    if qs is None:
        return []

    base = _annotate_severity_fields(qs)

    dist = (
        base.values("msg_sev_norm", "sev_norm")
        .annotate(total=Count("id"))
        .order_by()
    )

    counts = {
        "critical": 0,
        "high": 0,
        "medium": 0,
        "low": 0,
        "info": 0,
        "na": 0,
    }

    def classify(raw: str) -> str:
        raw = (raw or "").strip()
        if not raw or raw.lower() in {"n/a", "na", "none", "desconocido"}:
            return "na"
        r = raw.lower()
        if r in CRITICAL_TERMS:
            return "critical"
        if r in HIGH_TERMS:
            return "high"
        if r in MEDIUM_TERMS:
            return "medium"
        if r in LOW_TERMS:
            return "low"
        if r in INFO_TERMS:
            return "info"
        return "na"

    for row in dist:
        msg_raw = row.get("msg_sev_norm") or ""
        sev_raw = row.get("sev_norm") or ""
        n = row.get("total") or 0

        key = classify(msg_raw)
        if (not msg_raw) or key == "na":
            key = classify(sev_raw)

        counts[key] += n

    total = sum(counts.values()) or 1

    config = [
        ("critical", "Crítica", "sev-critical"),
        ("high", "Alta", "sev-high"),
        ("medium", "Media", "sev-medium"),
        ("na", "Sin información (N/A)", "sev-na"),
    ]

    summary = []
    for key, label, css in config:
        c = counts[key]
        pct = round(c * 100 / total)
        summary.append(
            {
                "key": key,
                "label": label,
                "css_class": css,
                "count": c,
                "percent": pct,
            }
        )

    return summary


def _home_last_days_range_utc(days: int = 7):
    """
    Retorna (dt_from_utc, dt_to_utc_exclusive) para últimos N días.
    """
    now = datetime.now(tz=dt_timezone.utc)
    start = now - timedelta(days=days)
    return start, now


def _home_last_days_dates_local(days: int = 7):
    """
    Lista de fechas (date) para últimos N días, en timezone local de Django.
    Útil para rellenar el gráfico con ceros.
    """
    tz = dj_timezone.get_current_timezone()
    today_local = dj_timezone.localtime(dj_timezone.now(), timezone=tz).date()
    start = today_local - timedelta(days=days - 1)
    return [start + timedelta(days=i) for i in range(days)]


def _first_existing_dt_field(model, candidates: list[str]) -> str | None:
    """
    Devuelve el primer campo datetime/date existente en el modelo (por nombre).
    """
    try:
        field_names = {f.name for f in model._meta.get_fields()}
    except Exception:
        return None
    for name in candidates:
        if name in field_names:
            return name
    return None



def _get_contract_expiry_warning(tenant) -> dict | None:
    """
    Verifica si el contrato del tenant está próximo a expirar.
    
    Retorna un dict con:
    - 'days_remaining': días hasta la expiración
    - 'expiry_date': fecha de expiración (string formato YYYY-MM-DD)
    - 'support_plan': tipo de plan de soporte
    
    O None si no hay contrato o no está próximo a expirar.
    
    Lógica:
    - Si support_plan contiene "POC": alerta con 7 días o menos
    - Si support_plan contiene "Inntesec Agent": alerta con 30 días o menos
    - Cualquier otro plan: alerta con 30 días o menos (por defecto)
    """
    if not tenant or not hasattr(tenant, 'id'):
        return None
    
    try:
        today = dj_timezone.localdate()
        
        # Obtener el contrato activo más reciente del tenant
        contract = Tenants_contracts.objects.filter(
            tenant_id=tenant.id
        ).order_by('-expiry_date').first()
        
        if not contract:
            return None
        
        # Calcular días restantes
        days_remaining = (contract.expiry_date - today).days
        
        # Determinar el threshold según el support_plan (buscar texto contenido)
        support_plan = (contract.support_plan or "").strip()
        support_plan_lower = support_plan.lower()
        threshold_days = 30  # Por defecto 30 días
        
        # Verificar si contiene "POC"
        if "poc" in support_plan_lower:
            threshold_days = 7
        # Verificar si contiene "inntesec agent" o "agent"
        elif "inntesec agent" in support_plan_lower or "agent" in support_plan_lower:
            threshold_days = 30
        
        # Solo mostrar alerta si está dentro del threshold (incluso si ha expirado)
        if days_remaining <= threshold_days:
            return {
                'days_remaining': days_remaining,
                'expiry_date': contract.expiry_date.isoformat(),
                'support_plan': support_plan,
                'contract_name': contract.contract_name,
            }
        
        return None
        
    except Exception as e:
        logger.exception("[HOME] Error verificando contrato próximo a expirar: %s", e)
        return None

@login_required
@tenant_required
def home_index(request):
    tenant = getattr(request, "tenant", None)
    user = request.user

    # ─────────────────────────────────────────────
    # Permiso para ver la parte de monitorización
    # ─────────────────────────────────────────────
    can_view_monitoring = False
    try:
        effective_tenant = tenant or getattr(user, "tenant", None)
        if effective_tenant:
            alarms_id = (getattr(effective_tenant, "alarms_one_id", "") or "").strip()
            logs_id = (getattr(effective_tenant, "logs360siem_id", "") or "").strip()
            site_id = (getattr(effective_tenant, "site24x7_id", "") or "").strip()
            can_view_monitoring = any([
                alarms_id not in ("", "0"),
                logs_id not in ("", "0"),
                site_id not in ("", "0"),
            ])
    except Exception as e:
        logger.exception("[HOME] Error calculando can_view_monitoring: %s", e)
        can_view_monitoring = False

    norm_tid = _normalize_tenant_aotag(tenant) if tenant else ""

    # =======================
    # KPIs Alarmas / SOAR
    # =======================
    alarms_total = 0
    alarms_critical_total = 0
    alarms_daily_labels: list[str] = []
    alarms_daily_total: list[int] = []
    alarms_daily_critical: list[int] = []
    severity_summary: list[dict] = []

    if can_view_monitoring and norm_tid:
        # últimos 7 días por defecto
        dt_from_utc, dt_to_utc_exclusive = _home_last_days_range_utc(days=7)
        days_local = _home_last_days_dates_local(days=7)
        tz = dj_timezone.get_current_timezone()

        try:
            qs_base = make_base_qs(dt_from_utc, dt_to_utc_exclusive)
            qs_base = _annotate_severity_fields(qs_base)

            # KPIs últimos 7 días
            alarms_total = qs_base.count()
            alarms_critical_total = qs_base.filter(CRITICAL_FILTER).count()

            # Serie diaria últimos 7 días (rellena días sin datos)
            daily_qs = qs_base.exclude(event_time__isnull=True)
            daily = (
                daily_qs
                .annotate(day=TruncDate("event_time", tzinfo=tz))
                .values("day")
                .annotate(
                    total=Count("id"),
                    critical=Count("id", filter=CRITICAL_FILTER),
                )
                .order_by("day")
            )

            day_map = {row["day"]: row for row in daily}

            for d in days_local:
                alarms_daily_labels.append(d.isoformat())
                row = day_map.get(d)
                alarms_daily_total.append(int(row["total"]) if row else 0)
                alarms_daily_critical.append(int(row["critical"]) if row else 0)

            # Severidades últimos 7 días
            severity_summary = _build_severity_summary(qs_base)

        except Exception:
            # fallback por si make_base_qs falla
            try:
                qs_fallback = _annotate_norm_field(
                    Alarm.objects.all(), "tags", "norm_aotag"
                )
                base_fb = qs_fallback.filter(norm_aotag=norm_tid)
                base_fb = _annotate_severity_fields(base_fb)

                # IMPORTANTÍSIMO: aplicar rango 7 días en fallback también
                base_fb = base_fb.filter(
                    event_time__gte=dt_from_utc,
                    event_time__lt=dt_to_utc_exclusive,
                )

                alarms_total = base_fb.count()
                alarms_critical_total = base_fb.filter(CRITICAL_FILTER).count()

                daily_fb = (
                    base_fb
                    .exclude(event_time__isnull=True)
                    .annotate(day=TruncDate("event_time", tzinfo=tz))
                    .values("day")
                    .annotate(
                        total=Count("id"),
                        critical=Count("id", filter=CRITICAL_FILTER),
                    )
                    .order_by("day")
                )

                day_map = {row["day"]: row for row in daily_fb}

                for d in days_local:
                    alarms_daily_labels.append(d.isoformat())
                    row = day_map.get(d)
                    alarms_daily_total.append(int(row["total"]) if row else 0)
                    alarms_daily_critical.append(int(row["critical"]) if row else 0)

                severity_summary = _build_severity_summary(base_fb)

            except Exception as e:
                logger.exception("[HOME] Error KPI Alarmas (fallback): %s", e)

    # =======================
    # KPI SOAR (últimos 7 días)
    # =======================
    soar_total = 0
    if can_view_monitoring and norm_tid:
        try:
            # rango en fecha local (sin hora)
            today = dj_timezone.localdate()
            from_date = today - dj_timezone.timedelta(days=6)  # incluye hoy => 7 días

            qs_soar = _annotate_norm_field(
                IncidenteSOAR.objects.all(), "aotag", "norm_aotag"
            )

            soar_total = qs_soar.filter(
                norm_aotag=norm_tid,
                date__isnull=False,
                date__gte=from_date,
                date__lte=today,
            ).count()

        except Exception as e:
            logger.exception("[HOME] Error KPI SOAR: %s", e)

    # =======================
    # KPI Telegram
    # =======================
    user_tid = _get_user_telegram_id(user)
    telegram_total = 0
    try:
        if can_view_monitoring and user_tid:
            norm1 = _normalize_string_local(user_tid)
            norm_opts = {norm1}
            if norm1.startswith("@"):
                norm_opts.add(norm1[1:])
            qs_tel = _annotate_norm_field(
                TelegramSolicitud.objects.all(), "chat_id", "norm_chat"
            )
            telegram_total = qs_tel.filter(norm_chat__in=list(norm_opts)).count()
    except Exception as e:
        logger.exception("[HOME] Error KPI Telegram: %s", e)

    # =======================
    # Selector de tenant
    # =======================
    all_tenants = []
    user_tenant = getattr(user, "tenant", None)
    if user_tenant and str(user_tenant.name).lower() == "inntesec":
        all_tenants = Tenant.objects.all().order_by("name")

    # =======================
    # Buscadores IP
    # =======================
    blacklist_q_raw = (request.GET.get("blacklist_q") or "").strip()
    whitelist_q_raw = (request.GET.get("whitelist_q") or "").strip()
    blacklist_removed_raw = (request.GET.get("blacklist_removed") or "").strip()
    whitelist_removed_raw = (request.GET.get("whitelist_removed") or "").strip()

    # DBG: punto 1 (inputs)
    logger.info("[DBG WL] GET whitelist_q='%s'", whitelist_q_raw)

    blacklist_terms = _split_search_terms(blacklist_q_raw)
    whitelist_terms = _split_search_terms(whitelist_q_raw)
    blacklist_removed_terms = _split_search_terms(blacklist_removed_raw)
    whitelist_removed_terms = _split_search_terms(whitelist_removed_raw)

    # DBG: punto 1 (terms)
    logger.info(
        "[DBG WL] whitelist_q_raw='%s' whitelist_terms=%s",
        whitelist_q_raw,
        whitelist_terms,
    )
    logger.info(
        "[DBG WL] removed_raw='%s' removed_terms=%s",
        whitelist_removed_raw,
        whitelist_removed_terms,
    )

    blacklist_results = IPBlacklist.objects.none()

    # =======================
    # BLACKLIST
    # =======================
    if blacklist_terms:
        try:
            q_obj = Q()
            for term in blacklist_terms:
                q_obj |= Q(ip__icontains=term)
            qs_bl = IPBlacklist.objects.filter(q_obj)
            if blacklist_removed_terms:
                qs_bl = qs_bl.exclude(ip__in=blacklist_removed_terms)
            qs_bl = qs_bl.order_by("ip", "-fecha_actualizacion")
            blacklist_results = qs_bl
        except Exception as e:
            logger.exception("[HOME] Error búsqueda blacklist: %s", e)

    # =================================================
    # WHITELIST (tabla + modal; países solo preferencia)
    # =================================================
    whitelist_results = IPWhitelist.objects.none()
    whitelist_not_found_terms: list[str] = []
    show_whitelist_modal = False

    # 1) Leer países seleccionados desde las preferencias (POR TENANT) -> NOMBRES
    effective_tenant_for_pref = tenant or getattr(user, "tenant", None)
    try:
        if effective_tenant_for_pref:
            pref = WhitelistCountryPreference.objects.get(tenant=effective_tenant_for_pref)
            selected_paises = _ensure_list_of_str(getattr(pref, "paises", None))
        else:
            selected_paises = []
    except WhitelistCountryPreference.DoesNotExist:
        selected_paises = []
    except Exception as e:
        logger.exception("[HOME WHITELIST] Error leyendo preferencias de países: %s", e)
        selected_paises = []

    # Convertir NOMBRES (BD) -> CÓDIGOS (UI)
    CODE_BY_NAME = {v: k for k, v in COUNTRY_BY_CODE.items()}
    selected_country_codes = [CODE_BY_NAME.get(n) for n in (selected_paises or [])]
    selected_country_codes = [c for c in selected_country_codes if c]

    # 2) Base: whitelist del tenant (sin filtro por país, solo tenant)
    whitelist_base = IPWhitelist.objects.annotate(ip_txt=Cast(F("ip"), TextField()))

    if tenant:
        t_name = (getattr(tenant, "name", "") or "").strip()
        t_id = getattr(tenant, "id", None)

        logger.info(
            "[HOME WHITELIST] Filtrando whitelist por tenant_id=%s o cliente/organizacion(iexact)='%s'",
            t_id,
            t_name,
        )

        q = Q()
        if t_id is not None:
            q |= Q(tenant_id=t_id)
        if t_name:
            q |= Q(cliente__iexact=t_name) | Q(organizacion__iexact=t_name)

        whitelist_base = whitelist_base.filter(q) if q else IPWhitelist.objects.none()
    else:
        # Si no hay tenant, por seguridad no mostramos nada
        whitelist_base = IPWhitelist.objects.none()

    # 3) Excluir IPs “removidas” SIEMPRE (afecta tabla y chequeo de existencia)
    if whitelist_removed_terms:
        whitelist_base = whitelist_base.exclude(ip__in=whitelist_removed_terms)

    # 4) Tabla final parte desde la base (tenant + removed)
    whitelist_table = whitelist_base.order_by("ip", "-fecha_actualizacion")

    # DBG: punto 1 (counts base/tabla antes de buscar)
    try:
        t_name_dbg = (getattr(tenant, "name", "") or "").strip() if tenant else ""
        t_id_dbg = getattr(tenant, "id", None) if tenant else None
        base_count = whitelist_base.count()
        table_count_before_search = whitelist_table.count()
        logger.info(
            "[DBG WL] tenant_name='%s' tenant_id=%s base_count=%s table_count_before_search=%s",
            t_name_dbg,
            t_id_dbg,
            base_count,
            table_count_before_search,
        )
    except Exception as e:
        logger.exception("[DBG WL] error calculando counts pre-search: %s", e)

    # 5) Aplicar búsqueda (OR por cada término) y hacer que la TABLA muestre esos resultados
    if whitelist_terms:
        try:
            q_wl = Q()
            for term in whitelist_terms:
                q_wl |= Q(ip_txt__icontains=term)

            whitelist_table = whitelist_table.filter(q_wl)

            # DBG: punto 1 (SQL + count post-search)
            try:
                logger.info("[DBG WL] search_sql=%s", str(whitelist_table.query))
            except Exception:
                logger.exception("[DBG WL] error logeando search_sql")

            try:
                table_count_after_search = whitelist_table.count()
                logger.info("[DBG WL] table_count_after_search=%s", table_count_after_search)
            except Exception:
                logger.exception("[DBG WL] error calculando table_count_after_search")

            # Compatibilidad: si tu template usa whitelist_results, queda igual a la tabla
            whitelist_results = whitelist_table

            # “No encontrado” por término (correcto para búsquedas parciales)
            # Un término se considera encontrado si existe al menos una IP que lo contenga
            not_found = []
            for term in whitelist_terms:
                if not whitelist_base.filter(ip_txt__icontains=term).exists():
                    not_found.append(term)

            whitelist_not_found_terms = not_found
            show_whitelist_modal = bool(whitelist_not_found_terms)

        except Exception as e:
            logger.exception("[HOME] Error búsqueda whitelist: %s", e)
            whitelist_results = whitelist_table
    else:
        whitelist_results = whitelist_table

    # =======================
    # Credenciales descarga TXT
    # =======================
    cred = None
    try:
        if tenant:
            cred = TenantCredentials.get_active_for_tenant(
                int(getattr(tenant, "id", 0))
            )
    except Exception as e:
        logger.exception("[HOME] Error obteniendo credenciales del tenant: %s", e)

    # =======================
    # Verificar contrato próximo a expirar
    # =======================
    contract_warning = _get_contract_expiry_warning(tenant)

    # ============================
    # Preferencias de notificación
    # ============================
    tel_baja = tel_media = tel_alta = tel_critica = False
    mail_baja = mail_media = mail_alta = mail_critica = False
    tg_baja = tg_media = tg_alta = tg_critica = False

    try:
        notif_pref = NotificationChannelPreference.objects.get(user=user)
        t = notif_pref.telefono or {}
        m = notif_pref.correo or {}
        g = notif_pref.telegram or {}

        tel_baja = bool(t.get("baja"))
        tel_media = bool(t.get("media"))
        tel_alta = bool(t.get("alta"))
        tel_critica = bool(t.get("critica"))

        mail_baja = bool(m.get("baja"))
        mail_media = bool(m.get("media"))
        mail_alta = bool(m.get("alta"))
        mail_critica = bool(m.get("critica"))

        tg_baja = bool(g.get("baja"))
        tg_media = bool(g.get("media"))
        tg_alta = bool(g.get("alta"))
        tg_critica = bool(g.get("critica"))

    except NotificationChannelPreference.DoesNotExist:
        pass
    except Exception as e:
        logger.exception("[HOME] Error leyendo NotificationChannelPreference: %s", e)

    ctx = {
        "tenant": tenant,
        "all_tenants": all_tenants,
        "can_view_monitoring": can_view_monitoring,
        # KPIs
        "alarms_total": alarms_total,
        "alarms_critical_total": alarms_critical_total,
        "soar_total": soar_total,
        "telegram_total": telegram_total,
        "debug_user_telegram_id": user_tid or "",
        # Serie diaria
        "alarms_daily_labels_json": json.dumps(alarms_daily_labels),
        "alarms_daily_total_json": json.dumps(alarms_daily_total),
        "alarms_daily_critical_json": json.dumps(alarms_daily_critical),
        # Resumen severidad
        "severity_summary": severity_summary,
        # Blacklist
        "blacklist_q": blacklist_q_raw,
        "blacklist_terms": blacklist_terms,
        "blacklist_removed": blacklist_removed_raw,
        "blacklist_removed_terms": blacklist_removed_terms,
        "blacklist_results": blacklist_results,
        # Whitelist
        "whitelist_q": whitelist_q_raw,
        "whitelist_terms": whitelist_terms,
        "whitelist_removed": whitelist_removed_raw,
        "whitelist_removed_terms": whitelist_removed_terms,
        "whitelist_results": whitelist_results,
        "whitelist_table": whitelist_table,
        "whitelist_not_found_terms": whitelist_not_found_terms,
        "show_whitelist_modal": show_whitelist_modal,
        "whitelist_countries": ALL_COUNTRIES,
        # desde BD
        "selected_paises": selected_paises,
        # para marcar checkboxes (value=CL,AR,...)
        "selected_country_codes": selected_country_codes,
        # Credenciales TXT
        "cred": cred,
        # Preferencias notificaciones
        "tel_baja": tel_baja,
        "tel_media": tel_media,
        "tel_alta": tel_alta,
        "tel_critica": tel_critica,
        "mail_baja": mail_baja,
        "mail_media": mail_media,
        "mail_alta": mail_alta,
        "mail_critica": mail_critica,
        "tg_baja": tg_baja,
        "tg_media": tg_media,
        "tg_alta": tg_alta,
        "tg_critica": tg_critica,
        # Contrato próximo a expirar
        "contract_warning": contract_warning,

    }

    # DBG: punto 1 (ctx sanity)
    try:
        wr_count = whitelist_results.count() if whitelist_results is not None else None
        wt_count = whitelist_table.count() if whitelist_table is not None else None
        logger.info("[DBG WL] ctx: whitelist_results_count=%s whitelist_table_count=%s", wr_count, wt_count)

        first_ip_results = (
            whitelist_results.values_list("ip", flat=True).first()
            if whitelist_results is not None else None
        )
        first_ip_table = (
            whitelist_table.values_list("ip", flat=True).first()
            if whitelist_table is not None else None
        )
        logger.info(
            "[DBG WL] ctx: first_ip_results=%r first_ip_table=%r",
            first_ip_results,
            first_ip_table,
        )
    except Exception:
        logger.exception("[DBG WL] error logeando ctx sanity")

    return render(request, "home/index.html", ctx)


@login_required
@tenant_required
def blacklist_create_ticket(request):
    is_ajax = request.headers.get("x-requested-with") == "XMLHttpRequest"

    if request.method != "POST":
        if is_ajax:
            return JsonResponse(
                {"ok": False, "message": "Método no permitido."},
                status=405,
            )
        return HttpResponseRedirect(reverse("home:index"))

    ip_value = (request.POST.get("ip") or "").strip()
    if not ip_value:
        msg = "No se recibió una IP válida."
        if is_ajax:
            return JsonResponse({"ok": False, "message": msg}, status=400)
        messages.error(request, msg)
        return HttpResponseRedirect(reverse("home:index"))

    blacklist_q_original = (request.POST.get("blacklist_q_original") or "").strip()
    blacklist_removed_original = (request.POST.get("blacklist_removed_original") or "").strip()

    original_terms = _split_search_terms(blacklist_q_original)
    removed_terms = _split_search_terms(blacklist_removed_original)

    user = request.user
    try:
        tenant_user = TenantUser.objects.filter(user=user).first()
    except Exception:
        tenant_user = None
    id_usuario = str(tenant_user.id if tenant_user else user.id)
    nombre_usuario = user.get_full_name() or user.username

    webhook_url = os.getenv("WEBHOOK_URL", "").strip()
    passkey = os.getenv("PASSKEY", "").strip()
    if not webhook_url or not passkey:
        msg = "No se pudo enviar la solicitud. Intenta nuevamente más tarde."
        if is_ajax:
            return JsonResponse({"ok": False, "message": msg}, status=500)

        messages.error(request, "No se pudo enviar la solicitud. Webhook no está configurado.")
        params = {}
        if blacklist_q_original:
            params["blacklist_q"] = blacklist_q_original
        if blacklist_removed_original:
            params["blacklist_removed"] = blacklist_removed_original
        redirect_url = reverse("home:index")
        if params:
            redirect_url += "?" + urlencode(params)
        return HttpResponseRedirect(redirect_url)

    headers = {"passkey": passkey}
    params_webhook = {
        "value": "crear_ticket",
        "ip": ip_value,
        "id_usuario": id_usuario,
        "nombre_usuario": nombre_usuario,
        "type": "blacklist",
    }

    try:
        resp = requests.get(webhook_url, headers=headers, params=params_webhook, timeout=10)
        logger.info(
            "[BLACKLIST] Webhook respondió %s. Body (primeros 500 chars): %s",
            resp.status_code,
            resp.text[:500],
        )

        if resp.status_code >= 400:
            resp.raise_for_status()

        if ip_value not in removed_terms:
            removed_terms.append(ip_value)

        success_msg = f"Se envió la solicitud para eliminar la IP {ip_value} de la blacklist."

        if is_ajax:
            return JsonResponse({"ok": True, "message": success_msg}, status=200)

        messages.success(request, success_msg)

    except Exception as e:
        logger.exception("[BLACKLIST] Error llamando al webhook: %s", e)
        error_msg = "Ocurrió un error al enviar la solicitud. Intenta nuevamente más tarde."

        if is_ajax:
            return JsonResponse({"ok": False, "message": error_msg}, status=500)

        messages.error(request, "Ocurrió un error al enviar la solicitud al sistema de tickets.")

    all_removed = False
    if original_terms:
        try:
            existing_ips = list(
                IPBlacklist.objects.filter(ip__in=original_terms).values_list("ip", flat=True)
            )
            if existing_ips:
                all_removed = set(existing_ips).issubset(set(removed_terms))
        except Exception as e:
            logger.exception("[BLACKLIST] Error comprobando IPs restantes: %s", e)
    if all_removed:
        return HttpResponseRedirect(reverse("home:index"))

    params = {}
    if blacklist_q_original:
        params["blacklist_q"] = blacklist_q_original
    if removed_terms:
        params["blacklist_removed"] = ", ".join(removed_terms)
    redirect_url = reverse("home:index")
    if params:
        redirect_url += "?" + urlencode(params)
    return HttpResponseRedirect(redirect_url)


@login_required
@tenant_required
def whitelist_create_ticket(request):
    is_ajax = request.headers.get("x-requested-with") == "XMLHttpRequest"

    if request.method != "POST":
        if is_ajax:
            return JsonResponse(
                {"ok": False, "message": "Método no permitido."},
                status=405,
            )
        return HttpResponseRedirect(reverse("home:index"))

    ip_value = (request.POST.get("ip") or "").strip()
    if not ip_value:
        msg = "No se recibió una IP válida."
        if is_ajax:
            return JsonResponse({"ok": False, "message": msg}, status=400)
        messages.error(request, msg)
        return HttpResponseRedirect(reverse("home:index"))

    whitelist_q_original = (request.POST.get("whitelist_q_original") or "").strip()
    whitelist_removed_original = (request.POST.get("whitelist_removed_original") or "").strip()

    original_terms = _split_search_terms(whitelist_q_original)
    removed_terms = _split_search_terms(whitelist_removed_original)

    user = request.user
    try:
        tenant_user = TenantUser.objects.filter(user=user).first()
    except Exception:
        tenant_user = None

    id_usuario = str(tenant_user.id if tenant_user else user.id)
    nombre_usuario = user.get_full_name() or user.username

    webhook_url = os.getenv("WEBHOOK_URL", "").strip()
    passkey = os.getenv("PASSKEY", "").strip()

    if not webhook_url or not passkey:
        msg = "No se pudo enviar la solicitud. Intenta nuevamente más tarde."
        if is_ajax:
            return JsonResponse({"ok": False, "message": msg}, status=500)

        messages.error(
            request,
            "No se pudo enviar la solicitud de whitelist. Webhook no está configurado."
        )
        params = {}
        if whitelist_q_original:
            params["whitelist_q"] = whitelist_q_original
        if whitelist_removed_original:
            params["whitelist_removed"] = whitelist_removed_original

        redirect_url = reverse("home:index")
        if params:
            redirect_url += "?" + urlencode(params)
        return HttpResponseRedirect(redirect_url)

    headers = {"passkey": passkey}
    params_webhook = {
        "value": "crear_ticket",
        "ip": ip_value,
        "id_usuario": id_usuario,
        "nombre_usuario": nombre_usuario,
        "type": "whitelist",
    }

    try:
        resp = requests.get(
            webhook_url,
            headers=headers,
            params=params_webhook,
            timeout=30,
        )

        logger.info(
            "[WHITELIST] Webhook respondió %s. Body (primeros 500 chars): %s",
            resp.status_code,
            resp.text[:500],
        )

        if resp.status_code >= 400:
            resp.raise_for_status()

        if ip_value not in removed_terms:
            removed_terms.append(ip_value)

        success_msg = f"Se envió la solicitud para añadir la IP {ip_value} a la whitelist."

        if is_ajax:
            return JsonResponse({"ok": True, "message": success_msg}, status=200)

        messages.success(request, success_msg)

    except requests.exceptions.ReadTimeout:
        logger.error(
            "[WHITELIST] Timeout esperando respuesta del webhook (%s).", webhook_url
        )
        error_msg = "No se pudo enviar la solicitud. Intenta nuevamente más tarde."
        if is_ajax:
            return JsonResponse({"ok": False, "message": error_msg}, status=500)

        messages.error(
            request,
            "Hubo un problema al comunicarse con el sistema de tickets. Intenta nuevamente.",
        )
    except Exception as e:
        logger.exception("[WHITELIST] Error llamando al webhook: %s", e)
        error_msg = "No se pudo enviar la solicitud. Intenta nuevamente más tarde."
        if is_ajax:
            return JsonResponse({"ok": False, "message": error_msg}, status=500)

        messages.error(
            request,
            "Ocurrió un error al enviar la solicitud de whitelist."
        )

    all_removed = False
    if original_terms:
        try:
            existing_ips = list(
                IPWhitelist.objects.filter(ip__in=original_terms).values_list(
                    "ip", flat=True
                )
            )
            if existing_ips:
                all_removed = set(existing_ips).issubset(set(removed_terms))
        except Exception as e:
            logger.exception("[WHITELIST] Error comprobando IPs restantes: %s", e)

    if all_removed:
        return HttpResponseRedirect(reverse("home:index"))

    params = {}
    if whitelist_q_original:
        params["whitelist_q"] = whitelist_q_original
    if removed_terms:
        params["whitelist_removed"] = ", ".join(removed_terms)

    redirect_url = reverse("home:index")
    if params:
        redirect_url += "?" + urlencode(params)

    return HttpResponseRedirect(redirect_url)


# -----------------------------
#  DESCARGA POR BASIC (robots)
# -----------------------------
def blacklist_txt(request):
    """
    Descarga protegida por Basic Auth (TenantCredentials).
    No usamos login_required: la protección es solo por Basic.
    """
    realm = "Inntesec Blacklist"

    def _basic_challenge(message: str = "Auth required") -> HttpResponse:
        resp = HttpResponse(message, status=401, content_type="text/plain")
        resp["WWW-Authenticate"] = f'Basic realm="{realm}"'
        resp["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        resp["Pragma"] = "no-cache"
        return resp

    auth = (request.META.get("HTTP_AUTHORIZATION") or "").strip()

    logger.info("[BLACKLIST TXT] Llamada a blacklist_txt. Authorization='%s'", auth)

    if not auth.startswith("Basic "):
        logger.info("[BLACKLIST TXT] Sin cabecera Basic. Enviando challenge.")
        return _basic_challenge()

    try:
        raw = auth.split(" ", 1)[1].strip()
        userpass = base64.b64decode(raw).decode("utf-8")
        username, password = userpass.split(":", 1)
        username = (username or "").strip()
        password = (password or "").strip()
        logger.info("[BLACKLIST TXT] Credenciales recibidas username='%s'", username)
    except Exception:
        logger.exception("[BLACKLIST TXT] Error decodificando cabecera Basic")
        return _basic_challenge("Invalid authorization header")

    creds = _validate_creds(username, password)
    if not creds:
        logger.info("[BLACKLIST TXT] Credenciales inválidas para usuario=%s", username)
        return _basic_challenge("Invalid credentials")

    if not _has_any_service(creds):
        logger.info("[BLACKLIST TXT] Usuario sin servicios habilitados: %s", username)
        return HttpResponse("Forbidden", status=403, content_type="text/plain")

    try:
        now = dj_timezone.now()
        if not creds.first_login_at:
            creds.first_login_at = now
        creds.last_login_at = now
        creds.save(update_fields=["first_login_at", "last_login_at"])
        logger.info("[BLACKLIST TXT] Timestamps de login actualizados para creds_pk=%s", creds.pk)
    except Exception:
        logger.exception("[BLACKLIST TXT] No se pudo actualizar timestamps de login")

    logger.info("[BLACKLIST TXT] Llamando a _upsert_whitelist_from_download desde blacklist_txt")
    _upsert_whitelist_from_download(request, creds)

    return _stream_blacklist_txt_response()


def _stream_blacklist_txt_response() -> HttpResponse:
    try:
        ips_qs = IPBlacklist.objects.order_by("ip").values_list("ip", flat=True)

        ips = []
        for ip in ips_qs:
            if ip is None:
                continue
            ip_str = str(ip).strip()
            if not ip_str:
                continue
            ips.append(ip_str)

    except Exception as e:
        logger.exception("[BLACKLIST GET] Error consultando IPs: %s", e)
        return HttpResponse("Internal error", status=500, content_type="text/plain")

    body = "\n".join(ips)
    if body:
        body += "\n"

    resp = HttpResponse(body, content_type="text/plain; charset=utf-8")
    resp["Content-Disposition"] = 'attachment; filename="blacklist.txt"'
    resp["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    resp["Pragma"] = "no-cache"
    return resp


def _validate_creds(username: str, password: str) -> TenantCredentials | None:
    if not username or not password:
        return None

    # Compatibilidad: intento directo (valores en texto plano en BD)
    try:
        legacy = TenantCredentials.objects.filter(
            username=username,
            password=password,
            is_active=True,
        ).first()
        if legacy:
            logger.info(
                "[VALIDATE CREDS] Match directo (legacy) username='%s', creds_pk=%s",
                username,
                legacy.pk,
            )
            try:
                legacy.ensure_encrypted(persist=True)
            except Exception:
                logger.exception(
                    "[VALIDATE CREDS] No se pudo asegurar cifrado (legacy) username='%s'",
                    username,
                )
            return legacy
    except Exception:
        logger.exception("[VALIDATE CREDS] Error en match directo (legacy)")

    try:
        qs = TenantCredentials.objects.filter(is_active=True)
    except Exception:
        logger.exception("[VALIDATE CREDS] Error consultando credenciales activas")
        return None

    for creds in qs:
        try:
            if creds.username_plain == username and creds.password_plain == password:
                try:
                    creds.ensure_encrypted(persist=True)
                except Exception:
                    logger.exception(
                        "[VALIDATE CREDS] No se pudo asegurar cifrado para username='%s'",
                        username,
                    )

                logger.info(
                    "[VALIDATE CREDS] OK username='%s', creds_pk=%s, tenant_fk=%s",
                    username,
                    creds.pk,
                    getattr(creds, "tenant_id", None),
                )
                return creds
        except Exception:
            logger.exception(
                "[VALIDATE CREDS] Error evaluando credencial username='%s'",
                username,
            )

    logger.info(
        "[VALIDATE CREDS] No se encontraron credenciales activas para username='%s'",
        username,
    )
    return None

    logger.info(
        "[VALIDATE CREDS] No se encontraron credenciales activas para username='%s'",
        username,
    )
    return None


def _has_any_service(creds: TenantCredentials) -> bool:
    res = any([
        (creds.alarms_one_id or "").strip() not in ("", "0"),
        (creds.logs360siem_id or "").strip() not in ("", "0"),
        (creds.site24x7_id or "").strip() not in ("", "0"),
    ])
    logger.info(
        "[HAS ANY SERVICE] creds_pk=%s -> %s",
        getattr(creds, "pk", None),
        res,
    )
    return res


def _touch_login(creds: TenantCredentials) -> None:
    try:
        now = dj_timezone.now()
        if not creds.first_login_at:
            creds.first_login_at = now
        creds.last_login_at = now
        creds.save(update_fields=["first_login_at", "last_login_at"])
        logger.info("[TOUCH LOGIN] Timestamps actualizados para creds_pk=%s", creds.pk)
    except Exception:
        logger.exception("[BLACKLIST POST] No se pudo actualizar timestamps")


def _touch_tc_login(creds: TenantCredentials) -> None:
    _touch_login(creds)


@login_required
def blacklist_download_root(request):
    nonce = (request.GET.get("r") or "").strip()
    realm = f'Inntesec Blacklist {nonce}' if nonce else 'Inntesec Blacklist'

    auth = request.META.get("HTTP_AUTHORIZATION", "")

    logger.info(
        "[BLACKLIST ROOT] Llamada a blacklist_download_root. Authorization='%s', realm='%s'",
        auth,
        realm,
    )

    if not auth.startswith("Basic "):
        logger.info("[BLACKLIST ROOT] Sin cabecera Basic. Enviando challenge inicial.")
        resp = HttpResponse("Auth required", status=401, content_type="text/plain")
        resp["WWW-Authenticate"] = f'Basic realm="{realm}"'
        resp["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        resp["Pragma"] = "no-cache"
        return resp

    try:
        raw = auth.split(" ", 1)[1]
        userpass = base64.b64decode(raw).decode("utf-8")
        username, password = userpass.split(":", 1)
        username = (username or "").strip()
        password = (password or "").strip()
        logger.info("[BLACKLIST ROOT] Credenciales recibidas username='%s'", username)
    except Exception:
        logger.exception("[BLACKLIST ROOT] Error decodificando cabecera Basic")
        resp = HttpResponse("Invalid authorization header", status=401, content_type="text/plain")
        resp["WWW-Authenticate"] = f'Basic realm="{realm}"'
        resp["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        resp["Pragma"] = "no-cache"
        return resp

    creds = _validate_creds(username, password)
    if not creds or not _has_any_service(creds):
        logger.info(
            "[BLACKLIST ROOT] Unauthorized o sin servicios. username='%s', creds_ok=%s",
            username,
            bool(creds),
        )
        resp = HttpResponse("Unauthorized", status=401, content_type="text/plain")
        resp["WWW-Authenticate"] = f'Basic realm="{realm}"'
        resp["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        resp["Pragma"] = "no-cache"
        return resp

    logger.info(
        "[BLACKLIST ROOT] Credenciales OK. creds_pk=%s, llamando a _touch_login + _upsert_whitelist_from_download",
        creds.pk,
    )
    _touch_login(creds)
    _upsert_whitelist_from_download(request, creds)

    logger.info("[BLACKLIST ROOT] Redirigiendo a blacklist_download_page")
    return HttpResponseRedirect(reverse("home:blacklist_download_page"))


@login_required
def blacklist_download_page(request):
    logger.info("[BLACKLIST PAGE] Descarga TXT para usuario=%s", getattr(request.user, "username", None))
    return _stream_blacklist_txt_response()


@require_POST
def blacklist_download_post(request):
    client_ip = _get_client_ip(request)
    username = (request.POST.get("username") or "").strip()
    password = (request.POST.get("password") or "").strip()

    logger.info(
        "[BLACKLIST POST] Llamada a blacklist_download_post username='%s' ip=%s",
        username,
        client_ip,
    )

    creds = _validate_creds(username, password)
    if not creds or not _has_any_service(creds):
        logger.info("[BLACKLIST POST] invalid/no-service for %s ip=%s", username, client_ip)
        return HttpResponse(
            "Credenciales inválidas o sin servicio habilitado.",
            status=401,
            content_type="text/plain",
        )

    logger.info("[BLACKLIST POST] OK download for %s ip=%s creds_pk=%s", username, client_ip, creds.pk)
    _touch_login(creds)
    logger.info("[BLACKLIST POST] Llamando a _upsert_whitelist_from_download desde blacklist_download_post")
    _upsert_whitelist_from_download(request, creds)

    return _stream_blacklist_txt_response()


@login_required
@require_http_methods(["POST"])
def config_notificaciones(request):
    user = request.user
    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"

    logger.info("[CONFIG NOTIF] POST recibido para user_id=%s", getattr(user, "id", None))

    try:
        alarma_telefono = bool(request.POST.get("Alarma_Telefono"))
        alarma_correo = bool(request.POST.get("Alarma_Correo"))
        alarma_telegram = bool(request.POST.get("Alarma_Telegram"))

        logger.info(
            "[CONFIG NOTIF] Toggles -> tel=%s mail=%s tg=%s",
            alarma_telefono,
            alarma_correo,
            alarma_telegram,
        )

        raw_phone = (request.POST.get("phone") or request.POST.get("telefono") or "").strip()
        phone_value = None

        if raw_phone == "":
            phone_value = None
        else:
            phone_value = normalize_e164_phone(raw_phone)
            if phone_value is None:
                msg = (
                    "Número inválido. Usa formato internacional E.164, ej: +56912345678 o +14155552671."
                )
                if is_ajax:
                    return JsonResponse({"ok": False, "message": msg}, status=400)
                messages.error(request, msg)
                return HttpResponseRedirect(reverse("home:index"))

        tel_conf = {
            "baja": bool(request.POST.get("sev_tel_baja")),
            "media": bool(request.POST.get("sev_tel_media")),
            "alta": bool(request.POST.get("sev_tel_alta")),
            "critica": bool(request.POST.get("sev_tel_critica")),
        }
        if not alarma_telefono:
            tel_conf = {k: False for k in tel_conf}

        mail_conf = {
            "baja": bool(request.POST.get("sev_mail_baja")),
            "media": bool(request.POST.get("sev_mail_media")),
            "alta": bool(request.POST.get("sev_mail_alta")),
            "critica": bool(request.POST.get("sev_mail_critica")),
        }
        if not alarma_correo:
            mail_conf = {k: False for k in mail_conf}

        tg_conf = {
            "baja": bool(request.POST.get("sev_tg_baja")),
            "media": bool(request.POST.get("sev_tg_media")),
            "alta": bool(request.POST.get("sev_tg_alta")),
            "critica": bool(request.POST.get("sev_tg_critica")),
        }
        if not alarma_telegram:
            tg_conf = {k: False for k in tg_conf}

        logger.info("[CONFIG NOTIF] Tel=%s Mail=%s Tg=%s", tel_conf, mail_conf, tg_conf)

        raw_hora_inicio = (request.POST.get("hora_inicio") or "").strip()
        raw_hora_fin = (request.POST.get("hora_fin") or "").strip()

        if alarma_telefono:
            hora_inicio = raw_hora_inicio or user.hora_inicio
            hora_fin = raw_hora_fin or user.hora_fin
        else:
            hora_inicio = None
            hora_fin = None

        logger.info(
            "[CONFIG NOTIF] Franja -> inicio='%s' fin='%s' (alarma_telefono=%s)",
            hora_inicio,
            hora_fin,
            alarma_telefono,
        )

        with transaction.atomic():
            user.Alarma_Telefono = alarma_telefono
            user.Alarma_Correo = alarma_correo
            user.Alarma_Telegram = alarma_telegram
            user.phone = phone_value
            user.hora_inicio = hora_inicio
            user.hora_fin = hora_fin
            user.save(
                update_fields=[
                    "Alarma_Telefono",
                    "Alarma_Correo",
                    "Alarma_Telegram",
                    "phone",
                    "hora_inicio",
                    "hora_fin",
                ]
            )
            logger.info("[CONFIG NOTIF] Usuario actualizado OK (user_id=%s)", user.id)

            pref, created = NotificationChannelPreference.objects.get_or_create(user=user)
            pref.telefono = tel_conf
            pref.correo = mail_conf
            pref.telegram = tg_conf
            pref.save(update_fields=["telefono", "correo", "telegram"])

            logger.info(
                "[CONFIG NOTIF] Pref guardadas OK (pref_id=%s, created=%s)",
                getattr(pref, "id", None),
                created,
            )

        if is_ajax:
            return JsonResponse({"ok": True}, status=200)

        return HttpResponseRedirect(reverse("home:index"))

    except Exception:
        logger.exception("[CONFIG NOTIF] Error guardando preferencias (500)")
        if is_ajax:
            return JsonResponse(
                {"ok": False, "message": "Error interno al guardar preferencias."},
                status=500,
            )
        return HttpResponseRedirect(reverse("home:index"))


# Endpoint GET para cargar selección por tenant (devuelve nombres + códigos)
@login_required
@tenant_required
@require_GET
def whitelist_get_countries(request):
    tenant = getattr(request, "tenant", None) or getattr(request.user, "tenant", None)
    if not tenant:
        return JsonResponse({"ok": False, "message": "Tenant no resuelto."}, status=400)

    try:
        obj = WhitelistCountryPreference.objects.filter(tenant_id=tenant.id).only("paises").first()
        selected_paises = _ensure_list_of_str(getattr(obj, "paises", None)) if obj else []

        CODE_BY_NAME = {v: k for k, v in COUNTRY_BY_CODE.items()}
        selected_codes = [CODE_BY_NAME.get(n) for n in selected_paises]
        selected_codes = [c for c in selected_codes if c]

        return JsonResponse(
            {"ok": True, "selected_paises": selected_paises, "selected_codes": selected_codes},
            status=200,
        )
    except Exception as e:
        logger.exception("[HOME WHITELIST AJAX] GET error tenant_id=%s: %s", tenant.id, e)
        return JsonResponse(
            {"ok": False, "message": "Error interno al leer preferencias de países."},
            status=500,
        )


@login_required
@tenant_required
@require_http_methods(["POST"])
def whitelist_save_countries(request):
    tenant = getattr(request, "tenant", None) or getattr(request.user, "tenant", None)
    if not tenant:
        return JsonResponse({"ok": False, "message": "Tenant no resuelto."}, status=400)

    raw_country_codes = (request.POST.get("countries") or "").strip()
    codes_from_query = _parse_country_codes(raw_country_codes)

    # Solo códigos válidos
    selected_codes = [c for c in codes_from_query if c in COUNTRY_BY_CODE]

    # Se guardan nombres en BD (list[str])
    selected_paises = [COUNTRY_BY_CODE[c] for c in selected_codes]
    selected_paises = _ensure_list_of_str(selected_paises)

    try:
        WhitelistCountryPreference.objects.update_or_create(
            tenant_id=tenant.id,
            defaults={"paises": selected_paises},
        )

        return JsonResponse(
            {"ok": True, "selected_paises": selected_paises, "selected_codes": selected_codes},
            status=200,
        )
    except Exception as e:
        logger.exception("[HOME WHITELIST AJAX] SAVE error tenant_id=%s: %s", tenant.id, e)
        return JsonResponse(
            {"ok": False, "message": "Error interno al guardar preferencias de países."},
            status=500,
        )
