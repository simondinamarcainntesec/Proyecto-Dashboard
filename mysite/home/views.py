# home/views.py
from __future__ import annotations
from datetime import datetime, timezone as dt_timezone
import logging
import os
import base64
from urllib.parse import urlencode

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.db.models import F, Value, TextField, Q, Count
from django.db.models.functions import Lower, Replace, Trim, Cast, TruncDate
import json
from tenants.decorators import tenant_required
from tenants.models import Tenant, TenantUser

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
from django.views.decorators.http import require_POST, require_http_methods

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

# términos que reconocemos como severidades "normales" en msg_severity
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


# Filtro reutilizable para "alarmas críticas":
# - msg_severity es crítico, O
# - msg_severity no es una severidad conocida (vacío, notice, alert, etc.)
#   y severity indica crítico
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
    return [
        c.strip().upper()
        for c in raw.split(",")
        if c.strip()
    ]


def _save_country_pref(user, tenant, paises: list[str]) -> None:
    """
    Guarda en agent.whitelist_country_preference la lista de países (nombres)
    seleccionados por usuario (UN REGISTRO POR USER).

    - Siempre hay un único registro por user.
    - El campo tenant se actualiza con el tenant activo en el momento de guardar.
    - Si paises es [], se deja la preferencia vacía (filtro limpio).
    """
    from django.utils import timezone as _tz

    WhitelistCountryPreference.objects.update_or_create(
        user=user,
        defaults={
            "tenant": tenant,
            "paises": paises,
            "updated_at": _tz.now(),
        },
    )


# ──────────────────────────────────────────────────────────────────────────────
# Helper: IP del cliente (funciona con o sin proxy si Apache/Nginx está ok)
# ──────────────────────────────────────────────────────────────────────────────
def _get_client_ip(request) -> str:
    """
    Devuelve la IP del cliente. Si hay proxy/reverso, usa la primera de X-Forwarded-For.
    Asegúrate en prod de tener mod_remoteip (Apache) o real_ip (Nginx) configurado.
    """
    xff = (request.META.get("HTTP_X_FORWARDED_FOR") or "").strip()
    if xff:
        return xff.split(",")[0].strip()
    return (request.META.get("REMOTE_ADDR") or "").strip()


# ──────────────────────────────────────────────────────────────────────────────
# Upsert a agent.ip_whitelist al descargar: registra IP/cliente/tenant y fechas
# ──────────────────────────────────────────────────────────────────────────────
def _upsert_whitelist_from_download(
    request,
    creds: TenantCredentials | None = None,
) -> None:
    """
    Crea o actualiza un registro en agent.ip_whitelist:
      - ip                  -> IP pública del cliente
      - cliente             -> NOMBRE DEL TENANT que descarga
      - organizacion        -> NOMBRE DEL TENANT (igual que cliente)
      - motivo              -> 'Automatizado' (solo al crear)
      - fecha_creacion      -> now (solo al crear)
      - fecha_actualizacion -> now (siempre en descarga)
      - tenant_id           -> id del tenant actual (si se puede resolver)
                               (primero con tenant FK, luego con TenantCredentials)
    """
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

        # 1) Intentar sacar el tenant desde las credenciales (FK Tenant en TenantCredentials)
        tenant_obj = None
        if creds is not None:
            tenant_obj = getattr(creds, "tenant", None)
            logger.info(
                "[WHITELIST UPSERT] Tenant desde creds.tenant: %s",
                getattr(tenant_obj, "name", None),
            )

        # 2) Fallback a request.tenant o user.tenant
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

        # 3) Fallback usando agent.tenant_credentials (tenant_id / tenant_name)
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

        # Por requerimiento: cliente = nombre del tenant
        if not tenant_name:
            tenant_name = "Tenant desconocido"

        now = dj_timezone.now()

        logger.info(
            "[WHITELIST UPSERT] Antes de get_or_create: ip=%s, cliente='%s', tenant_id=%s",
            ip,
            tenant_name,
            tenant_id,
        )

        # get_or_create por IP (la IP debería ser única en la tabla)
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
            # Si ya existía la IP, actualizamos datos clave
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
    """
    Devuelve una lista de dicts con los niveles de severidad y sus conteos.
    Niveles: critical, high, medium, low, info, na (Sin información / N/A).

    - Primero intenta clasificar usando msg_severity.
    - Si msg_severity está vacío o cae en 'na/desconocido', usa severity.
    """
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
        # si msg_severity está vacío o cae en 'na', usamos severity
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
        dt_from_utc = datetime(1970, 1, 1, tzinfo=dt_timezone.utc)
        dt_to_utc_exclusive = datetime.now(tz=dt_timezone.utc)
        try:
            qs_base = make_base_qs(dt_from_utc, dt_to_utc_exclusive)
            # anotamos msg_severity + severity normalizados
            qs_base = _annotate_severity_fields(qs_base)

            alarms_total = qs_base.count()
            # KPI Alarmas críticas usando msg_severity + fallback a severity
            alarms_critical_total = qs_base.filter(CRITICAL_FILTER).count()

            daily_qs = qs_base.exclude(event_time__isnull=True)
            daily = (
                daily_qs
                .annotate(day=TruncDate("event_time"))
                .values("day")
                .annotate(
                    total=Count("id"),
                    critical=Count("id", filter=CRITICAL_FILTER),
                )
                .order_by("day")
            )

            for row in daily:
                alarms_daily_labels.append(str(row["day"]))
                alarms_daily_total.append(row["total"])
                alarms_daily_critical.append(row["critical"])

            severity_summary = _build_severity_summary(qs_base)

        except Exception:
            try:
                qs_fallback = _annotate_norm_field(
                    Alarm.objects.all(), "tags", "norm_aotag"
                )
                base_fb = qs_fallback.filter(norm_aotag=norm_tid)
                # anotamos severidades también en el fallback
                base_fb = _annotate_severity_fields(base_fb)

                alarms_total = base_fb.count()
                alarms_critical_total = base_fb.filter(CRITICAL_FILTER).count()

                daily_fb = (
                    base_fb
                    .exclude(event_time__isnull=True)
                    .annotate(day=TruncDate("event_time"))
                    .values("day")
                    .annotate(
                        total=Count("id"),
                        critical=Count("id", filter=CRITICAL_FILTER),
                    )
                    .order_by("day")
                )

                for row in daily_fb:
                    alarms_daily_labels.append(str(row["day"]))
                    alarms_daily_total.append(row["total"])
                    alarms_daily_critical.append(row["critical"])

                severity_summary = _build_severity_summary(base_fb)

            except Exception as e:
                logger.exception("[HOME] Error KPI Alarmas (fallback): %s", e)

    # =======================
    # KPI SOAR
    # =======================
    soar_total = 0
    if can_view_monitoring and norm_tid:
        try:
            qs_soar = _annotate_norm_field(
                IncidenteSOAR.objects.all(), "aotag", "norm_aotag"
            )
            soar_total = qs_soar.filter(norm_aotag=norm_tid).count()
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

    blacklist_terms = _split_search_terms(blacklist_q_raw)
    whitelist_terms = _split_search_terms(whitelist_q_raw)
    blacklist_removed_terms = _split_search_terms(blacklist_removed_raw)
    whitelist_removed_terms = _split_search_terms(whitelist_removed_raw)

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

    # =======================
    # WHITELIST (tabla + filtros por país + modal)
    # =======================
    whitelist_results = IPWhitelist.objects.none()
    whitelist_not_found_terms: list[str] = []
    show_whitelist_modal = False

    # 1) Determinar países seleccionados (preferencias)
    has_countries_param = "countries" in request.GET
    raw_country_codes = (request.GET.get("countries") or "").strip()
    codes_from_query = _parse_country_codes(raw_country_codes)

    if codes_from_query:
        # Hay países en la URL → convertir códigos ISO a nombres en español y guardar
        selected_paises = [
            COUNTRY_BY_CODE[code]
            for code in codes_from_query
            if code in COUNTRY_BY_CODE
        ]
        try:
            _save_country_pref(user, tenant, selected_paises)
        except Exception as e:
            logger.exception("[HOME WHITELIST] Error guardando preferencias de países: %s", e)

    elif has_countries_param:
        # Viene el parámetro 'countries' PERO vacío → limpiar preferencia (lista vacía)
        selected_paises = []
        try:
            _save_country_pref(user, tenant, [])
        except Exception as e:
            logger.exception("[HOME WHITELIST] Error limpiando preferencias de países: %s", e)

    else:
        # No viene 'countries' en la URL → cargar lo que haya guardado para el usuario
        try:
            pref = WhitelistCountryPreference.objects.get(user=user)
            selected_paises = pref.paises or []
        except WhitelistCountryPreference.DoesNotExist:
            selected_paises = []
        except Exception as e:
            logger.exception("[HOME WHITELIST] Error leyendo preferencias de países: %s", e)
            selected_paises = []

    # 2) Base: whitelist del tenant (listado)
    whitelist_table = IPWhitelist.objects.all()
    if tenant:
        t_name = (getattr(tenant, "name", "") or "").strip()
        t_id = getattr(tenant, "id", None)
        logger.info(
            "[HOME WHITELIST] Filtrando whitelist por tenant_id=%s o cliente/organizacion='%s'",
            t_id,
            t_name,
        )
        q = Q()
        if t_id is not None:
            q |= Q(tenant_id=t_id)
        if t_name:
            q |= Q(cliente=t_name) | Q(organizacion=t_name)
        if q:
            whitelist_table = whitelist_table.filter(q)
        else:
            whitelist_table = IPWhitelist.objects.none()

    # 3) Aplicar filtro por países seleccionados (si hay)
    if selected_paises:
        whitelist_table = whitelist_table.filter(pais__in=selected_paises)

    # 4) Búsqueda dentro de la whitelist del tenant (filtrada o no por país)
    if whitelist_terms:
        try:
            q_wl = Q()
            for term in whitelist_terms:
                q_wl |= Q(ip__icontains=term)

            qs_wl = whitelist_table.filter(q_wl)

            if whitelist_removed_terms:
                qs_wl = qs_wl.exclude(ip__in=whitelist_removed_terms)

            if qs_wl.exists():
                whitelist_table = qs_wl
                whitelist_results = qs_wl

                existing_ips = list(qs_wl.values_list("ip", flat=True))
                whitelist_not_found_terms = [
                    ip for ip in whitelist_terms if ip not in existing_ips
                ]
                show_whitelist_modal = bool(whitelist_not_found_terms)
            else:
                whitelist_results = IPWhitelist.objects.none()
                whitelist_not_found_terms = whitelist_terms
                show_whitelist_modal = True

        except Exception as e:
            logger.exception("[HOME] Error búsqueda whitelist: %s", e)
    else:
        # Sin búsqueda: mostramos todo el whitelist del tenant (filtrado por país si aplica)
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

    ctx = {
        "tenant": tenant,
        "all_tenants": all_tenants,
        # Permiso para ver la parte de monitorización
        "can_view_monitoring": can_view_monitoring,
        # KPIs
        "alarms_total": alarms_total,
        "alarms_critical_total": alarms_critical_total,
        "soar_total": soar_total,
        "telegram_total": telegram_total,
        "debug_user_telegram_id": user_tid or "",
        # Serie diaria para el gráfico (JSON para el template)
        "alarms_daily_labels_json": json.dumps(alarms_daily_labels),
        "alarms_daily_total_json": json.dumps(alarms_daily_total),
        "alarms_daily_critical_json": json.dumps(alarms_daily_critical),
        # Resumen de severidad
        "severity_summary": severity_summary,
        # Blacklist
        "blacklist_q": blacklist_q_raw,
        "blacklist_terms": blacklist_terms,
        "blacklist_removed": blacklist_removed_raw,
        "blacklist_removed_terms": blacklist_removed_terms,
        "blacklist_results": blacklist_results,
        # Whitelist (tabla + modal + filtro países)
        "whitelist_q": whitelist_q_raw,
        "whitelist_terms": whitelist_terms,
        "whitelist_removed": whitelist_removed_raw,
        "whitelist_removed_terms": whitelist_removed_terms,
        "whitelist_results": whitelist_results,
        "whitelist_table": whitelist_table,
        "whitelist_not_found_terms": whitelist_not_found_terms,
        "show_whitelist_modal": show_whitelist_modal,
        "whitelist_countries": ALL_COUNTRIES,
        "selected_paises": selected_paises,
        # Credenciales TXT
        "cred": cred,
    }
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
    try:
        creds = TenantCredentials.objects.get(
            username=username,
            password=password,
            is_active=True,
        )
        logger.info(
            "[VALIDATE CREDS] OK username='%s', creds_pk=%s, tenant_fk=%s",
            username,
            creds.pk,
            getattr(creds, "tenant_id", None),
        )
        return creds
    except TenantCredentials.DoesNotExist:
        logger.info(
            "[VALIDATE CREDS] No se encontraron credenciales activas para username='%s'",
            username,
        )
        return None
    except Exception:
        logger.exception(
            "[VALIDATE CREDS] Error inesperado buscando credenciales para username='%s'",
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
    """
    Endpoint /home_prueba_inntesec/blacklist/
    - Muestra Basic Auth del navegador
    - Valida contra TenantCredentials
    - Si OK -> registra login + IP en whitelist y redirige a /blacklist/page/
    """
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
    """
    Endpoint final /home_prueba_inntesec/blacklist/page/
    Se asume que ya pasó por el Basic Auth en blacklist_download_root.
    Aquí simplemente devolvemos el TXT usando el helper existente.
    """
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
