# tenants/views.py
import logging
import re
import json  # para armar input_data

import requests
from django.conf import settings

from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.contrib import messages
from django.db.models import Q
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.contrib.auth.decorators import login_required
from django.urls import reverse
from django.http import HttpResponseRedirect, JsonResponse
from tenants.models import Tenant, Client, NotificationChannelPreference  # añadimos Client
from tenants.context import current_tenant, current_tenant_source
from django.contrib.auth import update_session_auth_hash
from django.contrib.messages import get_messages
from utils.ms_email import enviar_correo_cambio_contrasena

logger = logging.getLogger(__name__)
User = get_user_model()

# ========================== API SOPORTE INNTESEC (USERS) ==========================

SUPORTE_BASE_URL = "https://soporte.inntesec.com/api/v3"
SUPORTE_USERS_ENDPOINT = f"{SUPORTE_BASE_URL}/users"


def fetch_soporte_users(start_index: int = 1, row_count: int = 100) -> dict:
    """
    Llama a la API de soporte (https://soporte.inntesec.com/api/v3/users)
    para obtener usuarios usando input_data en QUERYSTRING.

    Requiere SOPORTE_AUTHTOKEN en settings.py:

        SOPORTE_AUTHTOKEN = "tu_token_zoho_aqui"
    """
    authtoken = os.getenv("SOPORTE_AUTHTOKEN")
    if not authtoken:
        logger.error("[SoporteUsers] Falta settings.SOPORTE_AUTHTOKEN")
        raise RuntimeError("Falta SOPORTE_AUTHTOKEN en settings")

    headers = {
        "authtoken": authtoken,
    }

    # La API espera input_data como JSON en querystring
    payload = {
        "list_info": {
            "sort_field": "name",
            "sort_order": "asc",
            "start_index": start_index,
            "row_count": row_count,
        }
    }
    params = {
        "input_data": json.dumps(payload)
    }

    try:
        resp = requests.get(
            SUPORTE_USERS_ENDPOINT,
            headers=headers,
            params=params,
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        li = (data or {}).get("list_info", {}) or {}
        logger.info(
            "[SoporteUsers] OK start_index_req=%s row_count_req=%s "
            "start_index_resp=%s row_count_resp=%s has_more=%s",
            start_index,
            row_count,
            li.get("start_index"),
            li.get("row_count"),
            li.get("has_more_rows"),
        )
        return data
    except requests.RequestException as e:
        logger.exception(
            "[SoporteUsers] Error llamando a %s: %s",
            SUPORTE_USERS_ENDPOINT,
            e,
        )
        raise


def sync_soporte_clients() -> dict:
    """
    Recorre todas las páginas de la API de soporte y sincroniza
    los usuarios con empresa (account != None) en la tabla Client.

    - Hace update_or_create por id (que viene como string en la API).
    - Asocia el Client al Tenant cuya name coincide con account['name'].
    """
    start_index = 1
    row_count_request = 100
    max_loops = 50  # seguridad anti-bucle

    total_raw = 0
    created = 0
    updated = 0
    skipped_no_account = 0
    skipped_no_tenant = 0
    skipped_no_email = 0
    skipped_bad_id = 0

    seen_ids = set()  # evitar duplicados por id

    for loop in range(max_loops):
        logger.info("[SoporteSync] Pidiendo página start_index=%s", start_index)
        data = fetch_soporte_users(start_index=start_index, row_count=row_count_request)

        users = (data or {}).get("users", []) or []
        list_info = (data or {}).get("list_info", {}) or {}
        if not users:
            logger.info("[SoporteSync] Página sin usuarios, fin.")
            break

        total_raw += len(users)

        for u in users:
            uid = u.get("id")
            if not uid:
                continue

            # evitar procesar el mismo id otra vez si la API repite
            if uid in seen_ids:
                continue
            seen_ids.add(uid)

            account = u.get("account")
            if account is None:
                skipped_no_account += 1
                continue

            account_name = account.get("name")
            if not account_name:
                skipped_no_tenant += 1
                continue

            # Buscar Tenant por nombre de empresa
            tenant = Tenant.objects.filter(name__iexact=account_name).first()
            if not tenant:
                logger.warning(
                    "[SoporteSync] No se encontró Tenant para empresa '%s' (user_id=%s)",
                    account_name,
                    uid,
                )
                skipped_no_tenant += 1
                continue

            email = u.get("email_id")
            if not email:
                skipped_no_email += 1
                continue

            name = u.get("name") or ""
            phone = u.get("mobile") or u.get("phone")

            # id del Client es entero
            try:
                client_id = int(uid)
            except (TypeError, ValueError):
                logger.warning(
                    "[SoporteSync] id de usuario no numérico, se omite: %r", uid
                )
                skipped_bad_id += 1
                continue

            obj, created_flag = Client.objects.update_or_create(
                id=client_id,
                defaults={
                    "tenant": tenant,
                    "name": name,
                    "email": email,
                    "phone": phone,
                },
            )

            if created_flag:
                created += 1
            else:
                updated += 1

        has_more = list_info.get("has_more_rows", False)
        resp_start = list_info.get("start_index") or start_index
        resp_count = list_info.get("row_count") or len(users)

        logger.info(
            "[SoporteSync] Página procesada: resp_start=%s resp_count=%s has_more=%s",
            resp_start,
            resp_count,
            has_more,
        )

        if not has_more:
            logger.info("[SoporteSync] has_more_rows=False, fin de paginación.")
            break

        if resp_count <= 0:
            logger.warning("[SoporteSync] resp_count <= 0, se detiene para evitar bucle.")
            break

        # avanzar al siguiente bloque
        start_index = resp_start + resp_count

    summary = {
        "total_raw": total_raw,
        "total_unique_ids": len(seen_ids),
        "created": created,
        "updated": updated,
        "skipped_no_account": skipped_no_account,
        "skipped_no_tenant": skipped_no_tenant,
        "skipped_no_email": skipped_no_email,
        "skipped_bad_id": skipped_bad_id,
    }
    logger.info("[SoporteSync] Resumen sincronización: %s", summary)
    return summary


@login_required
def soporte_usuarios_view(request):
    """
    Devuelve una página concreta de usuarios de soporte Inntesec (API v3) como JSON.

    Endpoint de ejemplo:
        /tenants/soporte/usuarios/?start_index=1&row_count=100
    """
    try:
        start_index = int(request.GET.get("start_index", 1))
    except ValueError:
        start_index = 1

    try:
        row_count = int(request.GET.get("row_count", 100))
    except ValueError:
        row_count = 100

    try:
        data = fetch_soporte_users(start_index=start_index, row_count=row_count)
        return JsonResponse(data, safe=False)
    except Exception as e:
        logger.exception("[SoporteUsersView] Error obteniendo usuarios: %s", e)
        return JsonResponse(
            {"error": "No se pudo obtener la lista de usuarios desde soporte."},
            status=500,
        )


@login_required
def soporte_sync_clients_view(request):
    """
    Endpoint para lanzar la sincronización de usuarios con empresa
    hacia la tabla Client.

    Ejemplo:
        /tenants/soporte/sync_clients/
    """
    try:
        summary = sync_soporte_clients()
        return JsonResponse(summary, status=200)
    except Exception as e:
        logger.exception("[SoporteSyncView] Error sincronizando clientes: %s", e)
        return JsonResponse(
            {"error": "No se pudo sincronizar la tabla Client desde soporte."},
            status=500,
        )


# ========================== LOGIN ==========================

@never_cache
def tenant_login_view(request):
    """
    Login con identifier (email o username) + password.
    Opcional: POST['tenant'] para scope explícito.
    """

    # Limpia mensajes antiguos (de sesiones previas)
    storage = get_messages(request)
    for _ in storage:
        pass

    if request.method == "POST":
        identifier = request.POST.get("username")
        password = request.POST.get("password")
        form_tenant_name = request.POST.get("tenant")

        if not identifier or not password:
            messages.error(request, "Debes ingresar tu correo o usuario y contraseña.")
            return render(request, "auth/login.html", {"now": timezone.now()})

        # Si el usuario ya está autenticado, cerrar sesión antes
        if request.user.is_authenticated:
            logout(request)

        user = None

        # --- Si se especifica el tenant en el formulario ---
        if form_tenant_name:
            tenant = Tenant.objects.filter(name__iexact=form_tenant_name).first()
            if not tenant:
                messages.error(request, "Empresa no encontrada.")
                return render(request, "auth/login.html", {"now": timezone.now()})

            user = (
                User.objects.filter(
                    Q(email__iexact=identifier) | Q(username__iexact=identifier),
                    tenant=tenant,
                )
                .select_related("tenant")
                .first()
            )
            if not user:
                messages.error(request, "Credenciales inválidas.")
                return render(request, "auth/login.html", {"now": timezone.now()})

            user_auth = authenticate(
                request,
                username=user.username,
                password=password,
                tenant_name=tenant.name,
            )

        # --- Si no se especifica el tenant (autodetectar) ---
        else:
            user = (
                User.objects.filter(
                    Q(email__iexact=identifier) | Q(username__iexact=identifier)
                )
                .select_related("tenant")
                .first()
            )
            if not user:
                messages.error(request, "Credenciales inválidas.")
                return render(request, "auth/login.html", {"now": timezone.now()})

            tenant_name_guess = getattr(getattr(user, "tenant", None), "name", None)
            user_auth = authenticate(
                request,
                username=user.username,
                password=password,
                tenant_name=tenant_name_guess,
            )
            if user_auth is None:
                user_auth = authenticate(request, username=user.username, password=password)

        # --- Login exitoso ---
        if user_auth is not None:
            login(request, user_auth)  # 🔹 Aquí Django rota el CSRF token

            tenant = getattr(user_auth, "tenant", None)
            if tenant:
                request.session["tenant_id"] = tenant.id
                request.session["tenant_name"] = tenant.name
                logger.info(
                    "[Login] Ok user=%s tenant=%s (guardado en sesión).",
                    user_auth.username,
                    tenant.name,
                )
            else:
                request.session["tenant_id"] = None
                request.session["tenant_name"] = None
                logger.warning(
                    "[Login] Usuario autenticado sin tenant asociado: %s",
                    user_auth.username,
                )
                messages.warning(request, "Inicio de sesión sin tenant asociado.")

            # Redirigir inmediatamente para evitar reenvíos o tokens antiguos
            return redirect("/home/")

        # --- Credenciales inválidas ---
        messages.error(request, "Credenciales inválidas.")
        return render(request, "auth/login.html", {"now": timezone.now()})

    # --- GET (mostrar formulario) ---
    ctx = {
        "now": timezone.now(),
        "tenant_debug": {
            "request_tenant_id": getattr(getattr(request, "tenant", None), "id", None),
            "request_tenant_name": getattr(getattr(request, "tenant", None), "name", None),
            "request_tenant_source": getattr(request, "tenant_source", None),
            "ctx_tenant_name": getattr(current_tenant.get(), "name", None),
            "ctx_tenant_source": current_tenant_source.get(),
        },
    }
    return render(request, "auth/login.html", ctx)


# ========================== LOGOUT ==========================

@never_cache
def logout_view(request):
    """
    Cierra sesión y limpia tenant_id/tenant_name.
    """
    logout(request)
    request.session.flush()

    resp = HttpResponseRedirect(reverse("login"))
    resp["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    resp["Pragma"] = "no-cache"
    resp["Expires"] = "0"
    return resp


# ========================== SWITCH TENANT ==========================

@login_required
def switch_tenant(request, tenant_id):
    """
    Cambia el tenant activo en la sesión.
    Si el usuario pertenece a Inntesec, puede cambiar entre tenants.
    Redirige al dashboard correcto según la página origen.
    """
    user_tenant = getattr(request.user, "tenant", None)
    if not user_tenant or user_tenant.name.lower() != "inntesec":
        messages.error(request, "No tienes permiso para cambiar de empresa.")
        return redirect("dashboard:dashboard")

    tenant = Tenant.objects.filter(id=tenant_id).first()
    if not tenant:
        messages.error(request, "El tenant seleccionado no existe.")
        return redirect("dashboard:dashboard_realtime")

    # Guardar en sesión
    request.session["tenant_id"] = tenant.id
    request.session["tenant_name"] = tenant.name
    logger.info("[SwitchTenant] %s cambió a tenant %s", request.user.username, tenant.name)

    # Determinar destino según Referer
    referer = request.META.get("HTTP_REFERER", "")
    if "realtime" in referer.lower():
        logger.debug("[SwitchTenant] Redirigiendo a dashboard_realtime tras cambio de tenant.")
        return redirect("dashboard:dashboard_realtime")
    else:
        logger.debug("[SwitchTenant] Redirigiendo a dashboard histórico tras cambio de tenant.")
        return redirect("dashboard:dashboard")


@login_required
def cambiar_contraseña(request):
    if request.method == "POST":
        actual = request.POST.get("actual")
        nueva = request.POST.get("nueva")
        confirmar = request.POST.get("confirmar")

        # 🔸 Validaciones de seguridad
        if not request.user.check_password(actual):
            messages.error(request, "La contraseña actual no es correcta.")
        elif nueva != confirmar:
            messages.error(request, "Las contraseñas nuevas no coinciden.")
        elif len(nueva) < 8:
            messages.error(request, "La nueva contraseña debe tener al menos 8 caracteres.")
        elif not re.search(r"\d", nueva):
            messages.error(request, "La nueva contraseña debe incluir al menos un número.")
        elif not re.search(r"[!@#$%^&*(),.?\":{}|<>_\-+=/\\;'\[\]]", nueva):
            messages.error(
                request,
                "La nueva contraseña debe incluir al menos un carácter especial (como @, #, $, %, etc.)."
            )
        else:
            # Cambia la contraseña y mantiene la sesión activa
            request.user.set_password(nueva)
            request.user.save()
            update_session_auth_hash(request, request.user)

            success_msg = "✅ Contraseña cambiada correctamente."

            # Envío del correo de confirmación (diseño corporativo Inntesec)
            try:
                enviar_correo_cambio_contrasena(
                    email_destino=request.user.email,
                    nombre_usuario=(request.user.first_name or request.user.username),
                )
                success_msg += " Se ha enviado un correo de confirmación a tu dirección registrada."
            except Exception as e:
                # ⚠️ Si falla el envío, mostrar advertencia pero mantener éxito
                messages.warning(
                    request,
                    f"Contraseña cambiada, pero ocurrió un error al enviar el correo: {e}"
                )

            messages.success(request, success_msg)
            return redirect("cambiar_contrasena")

    # Limpieza de mensajes antiguos (por accesibilidad)
    storage = get_messages(request)
    for _ in storage:
        pass

    return render(request, "auth/cambiar_contrasena.html")


def csrf_failure_view(request, reason=""):
    """
    Vista personalizada para manejar fallos de verificación CSRF.
    Redirige al login con un mensaje claro para el usuario.
    """
    messages.error(
        request,
        "Tu sesión expiró o el formulario no es válido. Por favor, inicia sesión nuevamente."
    )
    return redirect("/login/")


def oauth2_callback(request):
    code = request.GET.get("code")
    if not code:
        return JsonResponse({"error": "Missing authorization code"}, status=400)

    # URL del token de Microsoft
    token_url = "https://login.microsoftonline.com/common/oauth2/v2.0/token"

    # Datos requeridos para el intercambio
    data = {
        "client_id": settings.MS_CLIENT_ID,
        "client_secret": settings.MS_CLIENT_SECRET,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": "https://ia.inntesec.com/rest/oauth2-credential/callback",
    }

    # Solicita el token a Microsoft
    response = requests.post(token_url, data=data)
    token_data = response.json()

    # Guarda o devuelve el token (según tu necesidad)
    return JsonResponse(token_data)


@login_required
def config_notificaciones_view(request):
    """Página o modal de configuración de notificaciones del usuario"""
    user = request.user

    # Crear/obtener el registro de preferencias de canal para este usuario
    prefs, _ = NotificationChannelPreference.objects.get_or_create(user=user)

    if request.method == "POST":
        # ==============================
        # Canales (como ya los tenías)
        # ==============================
        user.Alarma_Telefono = "Alarma_Telefono" in request.POST
        user.Alarma_Correo = "Alarma_Correo" in request.POST
        user.Alarma_Telegram = "Alarma_Telegram" in request.POST

        # 🔹 Franja horaria
        hora_inicio = request.POST.get("hora_inicio") or None
        hora_fin = request.POST.get("hora_fin") or None

        if user.Alarma_Telefono:
            user.hora_inicio = hora_inicio
            user.hora_fin = hora_fin
        else:
            user.hora_inicio = None
            user.hora_fin = None

        user.save()

        # ==============================
        # Severidades por canal
        # ==============================

        # Teléfono
        prefs.telefono = {
            "baja": "sev_tel_baja" in request.POST,
            "media": "sev_tel_media" in request.POST,
            "alta": "sev_tel_alta" in request.POST,
            "critica": "sev_tel_critica" in request.POST,
        }

        # Correo
        prefs.correo = {
            "baja": "sev_mail_baja" in request.POST,
            "media": "sev_mail_media" in request.POST,
            "alta": "sev_mail_alta" in request.POST,
            "critica": "sev_mail_critica" in request.POST,
        }

        # Telegram
        prefs.telegram = {
            "baja": "sev_tg_baja" in request.POST,
            "media": "sev_tg_media" in request.POST,
            "alta": "sev_tg_alta" in request.POST,
            "critica": "sev_tg_critica" in request.POST,
        }

        prefs.save()

        # Soporta tanto submit normal como AJAX (fetch)
        is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"
        if is_ajax:
            return JsonResponse({"ok": True})

        return redirect(request.META.get("HTTP_REFERER", "dashboard:dashboard_alarmsone"))

    # ==============================
    # GET: preparar datos para el template
    # ==============================
    tel = prefs.telefono or {}
    mail = prefs.correo or {}
    tg = prefs.telegram or {}

    ctx = {
        "user": user,

        # Teléfono
        "tel_baja": tel.get("baja", True),
        "tel_media": tel.get("media", True),
        "tel_alta": tel.get("alta", True),
        "tel_critica": tel.get("critica", True),

        # Correo
        "mail_baja": mail.get("baja", True),
        "mail_media": mail.get("media", True),
        "mail_alta": mail.get("alta", True),
        "mail_critica": mail.get("critica", True),

        # Telegram
        "tg_baja": tg.get("baja", True),
        "tg_media": tg.get("media", True),
        "tg_alta": tg.get("alta", True),
        "tg_critica": tg.get("critica", True),
    }

    return render(request, "tenants/config_notificaciones.html", ctx)
