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
from .models import TelegramSolicitud, IPBlacklist, IPWhitelist, TenantCredentials

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
def _upsert_whitelist_from_download(request) -> None:
    """
    Crea o actualiza un registro en agent.ip_whitelist:
      - ip                -> IP pública del cliente
      - cliente           -> correo/username del usuario autenticado
      - organizacion      -> nombre del tenant
      - motivo            -> 'ip_whitelist automatizada' (solo al crear)
      - fecha_creacion    -> now (solo al crear)
      - fecha_actualizacion -> now (siempre en descarga)
      - tenant_id         -> id del tenant actual
    Si la IP ya existe, solo se actualiza fecha_actualizacion (no se tocan otros campos).
    """
    ip = _get_client_ip(request)
    if not ip:
        return

    user = getattr(request, "user", None)
    email = (getattr(user, "email", None) or getattr(user, "username", None) or "").strip()

    tenant_obj = getattr(request, "tenant", None) or getattr(user, "tenant", None)
    tenant_name = (getattr(tenant_obj, "name", None) or "").strip()

    now = dj_timezone.now()

    obj, created = IPWhitelist.objects.get_or_create(
        ip=ip,
        defaults={
            "cliente": email,
            "organizacion": tenant_name,
            "fecha_creacion": now,
            "fecha_actualizacion": now,
            "motivo": "ip_whitelist automatizada",
            "tenant_id": getattr(tenant_obj, "id", None),
        },
    )

    if not created:
        # Solo toca fecha_actualizacion
        IPWhitelist.objects.filter(pk=ip).update(fecha_actualizacion=now)


def _build_severity_summary(qs):
    """
    Devuelve una lista de dicts con los niveles de severidad y sus conteos.
    Niveles: critical, high, medium, low, info, na (Sin información / N/A).
    Siempre filtrados por el mismo tenant que venga en la QS.
    """
    if qs is None:
        return []

    # normalizamos msg_severity → sev_norm (minúsculas, sin espacios raros)
    base = _annotate_norm_field(qs, "msg_severity", "sev_norm")

    dist = (
        base.values("sev_norm")
        .annotate(total=Count("id"))
        .order_by()
    )

    counts = {
        "critical": 0,
        "high": 0,
        "medium": 0,
        "low": 0,
        "info": 0,
        "na": 0,   # N/A / sin información
    }

    for row in dist:
        raw = (row.get("sev_norm") or "").strip()
        n = row.get("total") or 0

        if not raw or raw in {"n/a", "na", "none", "desconocido"}:
            key = "na"
        elif raw in {"critical", "critico", "crítica", "critica"}:
            key = "critical"
        elif raw in {"high", "alto"}:
            key = "high"
        elif raw in {"medium", "medio", "media"}:
            key = "medium"
        elif raw in {"low", "bajo"}:
            key = "low"
        elif raw in {"info", "informational", "informacion", "información"}:
            key = "info"
        else:
            # cualquier valor raro lo mandamos a "sin información"
            key = "na"

        counts[key] += n

    total = sum(counts.values()) or 1  # evitar división por 0

    # Solo mostramos 4 niveles en la tarjeta
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
                "key": key,          # critical, high, etc.
                "label": label,      # texto legible
                "css_class": css,    # clase CSS pill: sev-critical, etc.
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
    # (Alarmas / SOAR / Telegram / buscadores IP)
    # Lógica: solo si el tenant tiene algún servicio
    # alarms_one_id / logs360siem_id / site24x7_id
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

    # Series para el gráfico (por día)
    alarms_daily_labels: list[str] = []
    alarms_daily_total: list[int] = []
    alarms_daily_critical: list[int] = []

    # Resumen de severidad (por tenant)
    severity_summary: list[dict] = []

    if can_view_monitoring and norm_tid:
        dt_from_utc = datetime(1970, 1, 1, tzinfo=dt_timezone.utc)
        dt_to_utc_exclusive = datetime.now(tz=dt_timezone.utc)
        try:
            qs_base = make_base_qs(dt_from_utc, dt_to_utc_exclusive)

            # Totales globales
            alarms_total = qs_base.count()
            alarms_critical_total = qs_base.filter(
                msg_severity__iexact="critical"
            ).count()

            # Serie diaria: total vs críticas por día (event_time)
            daily_qs = qs_base.exclude(event_time__isnull=True)
            daily = (
                daily_qs
                .annotate(day=TruncDate("event_time"))
                .values("day")
                .annotate(
                    total=Count("id"),
                    critical=Count("id", filter=Q(msg_severity__iexact="critical")),
                )
                .order_by("day")
            )

            for row in daily:
                alarms_daily_labels.append(str(row["day"]))   # "YYYY-MM-DD"
                alarms_daily_total.append(row["total"])
                alarms_daily_critical.append(row["critical"])

            # 🔹 Resumen de severidad filtrado por el mismo tenant
            severity_summary = _build_severity_summary(qs_base)

        except Exception:
            # Fallback si make_base_qs falla
            try:
                qs_fallback = _annotate_norm_field(
                    Alarm.objects.all(), "tags", "norm_aotag"
                )

                base_fb = qs_fallback.filter(norm_aotag=norm_tid)

                # Totales
                alarms_total = base_fb.count()
                alarms_critical_total = base_fb.filter(
                    msg_severity__iexact="critical"
                ).count()

                # Serie diaria con fallback
                daily_fb = (
                    base_fb
                    .exclude(event_time__isnull=True)
                    .annotate(day=TruncDate("event_time"))
                    .values("day")
                    .annotate(
                        total=Count("id"),
                        critical=Count("id", filter=Q(msg_severity__iexact="critical")),
                    )
                    .order_by("day")
                )

                for row in daily_fb:
                    alarms_daily_labels.append(str(row["day"]))
                    alarms_daily_total.append(row["total"])
                    alarms_daily_critical.append(row["critical"])

                # 🔹 Resumen de severidad en el fallback (igual por tenant)
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
    # WHITELIST (tabla + modal)
    # =======================
    whitelist_results = IPWhitelist.objects.none()
    whitelist_not_found_terms: list[str] = []
    show_whitelist_modal = False

    # Base: whitelist del tenant (listado)
    whitelist_table = IPWhitelist.objects.all()
    if tenant:
        whitelist_table = whitelist_table.filter(tenant_id=getattr(tenant, "id", None))

    if whitelist_terms:
        try:
            # Buscar dentro del whitelist del tenant
            q_wl = Q()
            for term in whitelist_terms:
                q_wl |= Q(ip__icontains=term)

            qs_wl = whitelist_table.filter(q_wl)

            if whitelist_removed_terms:
                qs_wl = qs_wl.exclude(ip__in=whitelist_removed_terms)

            if qs_wl.exists():
                # Hay coincidencias → se muestran en la tabla
                whitelist_table = qs_wl
                whitelist_results = qs_wl

                existing_ips = list(qs_wl.values_list("ip", flat=True))
                whitelist_not_found_terms = [
                    ip for ip in whitelist_terms if ip not in existing_ips
                ]
                # Solo mostramos modal si hay alguna IP buscada que NO está
                show_whitelist_modal = bool(whitelist_not_found_terms)
            else:
                # No existe ninguna de las IP buscadas en la whitelist del tenant
                whitelist_results = IPWhitelist.objects.none()
                whitelist_not_found_terms = whitelist_terms
                show_whitelist_modal = True

        except Exception as e:
            logger.exception("[HOME] Error búsqueda whitelist: %s", e)
    else:
        # Sin búsqueda: mostramos todo el whitelist del tenant en la tabla
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
        # 🔹 Resumen de severidad (para la tarjeta al lado del gráfico)
        "severity_summary": severity_summary,
        # Blacklist
        "blacklist_q": blacklist_q_raw,
        "blacklist_terms": blacklist_terms,
        "blacklist_removed": blacklist_removed_raw,
        "blacklist_removed_terms": blacklist_removed_terms,
        "blacklist_results": blacklist_results,
        # Whitelist (tabla + modal)
        "whitelist_q": whitelist_q_raw,
        "whitelist_terms": whitelist_terms,
        "whitelist_removed": whitelist_removed_raw,
        "whitelist_removed_terms": whitelist_removed_terms,
        "whitelist_results": whitelist_results,          # listado actual para el tenant
        "whitelist_table": whitelist_table,              # alias para la tabla
        "whitelist_not_found_terms": whitelist_not_found_terms,
        "show_whitelist_modal": show_whitelist_modal,
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

    # --- flujo clásico (no AJAX) se mantiene igual ---
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


logger = logging.getLogger(__name__)


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

    # --- flujo clásico (no AJAX) se mantiene igual ---
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
        """
        Devuelve un 401 con cabecera WWW-Authenticate para que el navegador
        muestre el popup de usuario/contraseña.
        """
        resp = HttpResponse(message, status=401, content_type="text/plain")
        resp["WWW-Authenticate"] = f'Basic realm="{realm}"'
        resp["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        resp["Pragma"] = "no-cache"
        return resp

    auth = (request.META.get("HTTP_AUTHORIZATION") or "").strip()

    # 1) Sin cabecera -> lanzar challenge
    if not auth.startswith("Basic "):
        return _basic_challenge()

    # 2) Intentar decodificar usuario:password
    try:
        raw = auth.split(" ", 1)[1].strip()
        userpass = base64.b64decode(raw).decode("utf-8")
        username, password = userpass.split(":", 1)
        username = (username or "").strip()
        password = (password or "").strip()
    except Exception:
        logger.exception("[BLACKLIST TXT] Error decodificando cabecera Basic")
        return _basic_challenge("Invalid authorization header")

    # 3) Validar con TenantCredentials (usa tu helper)
    creds = _validate_creds(username, password)
    if not creds:
        logger.info("[BLACKLIST TXT] Credenciales inválidas para usuario=%s", username)
        # Volvemos a dar challenge para que puedan reintentar
        return _basic_challenge("Invalid credentials")

    # 4) Verificar que tenga algún servicio habilitado
    if not _has_any_service(creds):
        logger.info("[BLACKLIST TXT] Usuario sin servicios habilitados: %s", username)
        # 403: el navegador YA NO vuelve a pedir usuario/clave
        return HttpResponse("Forbidden", status=403, content_type="text/plain")

    # 5) Actualizar timestamps y registrar IP en whitelist
    try:
        now = dj_timezone.now()
        if not creds.first_login_at:
            creds.first_login_at = now
        creds.last_login_at = now
        creds.save(update_fields=["first_login_at", "last_login_at"])
    except Exception:
        logger.exception("[BLACKLIST TXT] No se pudo actualizar timestamps de login")

    _upsert_whitelist_from_download(request)

    # 6) Enviar el TXT
    return _stream_blacklist_txt_response()


# --------------------------------------------
#  Helpers de descarga POST (misma página)
# --------------------------------------------
def _stream_blacklist_txt_response() -> HttpResponse:
    try:
        # Obtenemos solo la columna ip, ordenada, en una lista "plana"
        ips_qs = IPBlacklist.objects.order_by("ip").values_list("ip", flat=True)

        ips = []
        for ip in ips_qs:
            if ip is None:
                # saltamos nulos para que no reviente el join
                continue
            ip_str = str(ip).strip()
            if not ip_str:
                # saltamos strings vacíos
                continue
            ips.append(ip_str)

    except Exception as e:
        logger.exception("[BLACKLIST GET] Error consultando IPs: %s", e)
        return HttpResponse("Internal error", status=500, content_type="text/plain")

    # Armamos el cuerpo del TXT
    body = "\n".join(ips)
    if body:
        body += "\n"  # salto de línea final solo si hay contenido

    resp = HttpResponse(body, content_type="text/plain; charset=utf-8")
    resp["Content-Disposition"] = 'attachment; filename="blacklist.txt"'
    resp["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    resp["Pragma"] = "no-cache"
    return resp


def _validate_creds(username: str, password: str) -> TenantCredentials | None:
    if not username or not password:
        return None
    try:
        return TenantCredentials.objects.get(username=username, password=password, is_active=True)
    except TenantCredentials.DoesNotExist:
        return None


def _has_any_service(creds: TenantCredentials) -> bool:
    return any([
        (creds.alarms_one_id or "").strip() not in ("", "0"),
        (creds.logs360siem_id or "").strip() not in ("", "0"),
        (creds.site24x7_id or "").strip() not in ("", "0"),
    ])


def _touch_login(creds: TenantCredentials) -> None:
    try:
        now = dj_timezone.now()
        if not creds.first_login_at:
            creds.first_login_at = now
        creds.last_login_at = now
        creds.save(update_fields=["first_login_at", "last_login_at"])
    except Exception:
        logger.exception("[BLACKLIST POST] No se pudo actualizar timestamps")


# Alias que faltaba (evita NameError)
def _touch_tc_login(creds: TenantCredentials) -> None:
    _touch_login(creds)


# --------------------------------------------
#  Página dedicada de Login + Descarga (GET/POST)
# --------------------------------------------
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

    # 1) Si no viene cabecera Basic -> forzamos prompt
    if not auth.startswith("Basic "):
        resp = HttpResponse("Auth required", status=401, content_type="text/plain")
        resp["WWW-Authenticate"] = f'Basic realm="{realm}"'
        resp["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        resp["Pragma"] = "no-cache"
        return resp

    # 2) Decodificar usuario:password
    try:
        raw = auth.split(" ", 1)[1]
        userpass = base64.b64decode(raw).decode("utf-8")
        username, password = userpass.split(":", 1)
    except Exception:
        resp = HttpResponse("Invalid authorization header", status=401, content_type="text/plain")
        resp["WWW-Authenticate"] = f'Basic realm="{realm}"'
        resp["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        resp["Pragma"] = "no-cache"
        return resp

    # 3) Validar credenciales contra TenantCredentials
    creds = _validate_creds(username, password)
    if not creds or not _has_any_service(creds):
        resp = HttpResponse("Unauthorized", status=401, content_type="text/plain")
        resp["WWW-Authenticate"] = f'Basic realm="{realm}"'
        resp["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        resp["Pragma"] = "no-cache"
        return resp

    # 4) Registrar login + actualizar whitelist con la IP de quien descarga
    _touch_login(creds)
    _upsert_whitelist_from_download(request)

    # 5) Si todo OK, redirigimos a la página final
    return HttpResponseRedirect(reverse("home:blacklist_download_page"))


@login_required
def blacklist_download_page(request):
    """
    Endpoint final /home_prueba_inntesec/blacklist/page/
    Se asume que ya pasó por el Basic Auth en blacklist_download_root.
    Aquí simplemente devolvemos el TXT usando el helper existente.
    """
    return _stream_blacklist_txt_response()


# --------------------------------------------
#  (Opcional) descarga por POST “antigua”
# --------------------------------------------
@require_POST
def blacklist_download_post(request):
    client_ip = _get_client_ip(request)
    username = (request.POST.get("username") or "").strip()
    password = (request.POST.get("password") or "").strip()

    creds = _validate_creds(username, password)
    if not creds or not _has_any_service(creds):
        logger.info("[BLACKLIST POST] invalid/no-service for %s ip=%s", username, client_ip)
        return HttpResponse(
            "Credenciales inválidas o sin servicio habilitado.",
            status=401,
            content_type="text/plain",
        )

    logger.info("[BLACKLIST POST] OK download for %s ip=%s", username, client_ip)
    _touch_login(creds)
    # 👇 registra/actualiza ip -> fecha_actualizacion
    _upsert_whitelist_from_download(request)

    return _stream_blacklist_txt_response()
