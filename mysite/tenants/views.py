# tenants/views.py
import logging
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.contrib import messages
from django.db.models import Q
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.contrib.auth.decorators import login_required
from django.urls import reverse
from django.http import HttpResponseRedirect
from tenants.models import Tenant
from tenants.context import current_tenant, current_tenant_source
from django.contrib.auth import update_session_auth_hash
import re
from django.contrib.messages import get_messages
from utils.ms_email import enviar_correo_cambio_contrasena

logger = logging.getLogger(__name__)
User = get_user_model()

# ========================== LOGIN ==========================
@never_cache
def tenant_login_view(request):
    """
    Login con identifier (email o username) + password.
    Opcional: POST['tenant'] para scope explícito.
    """

    # ✅ Limpia mensajes antiguos (de sesiones previas)
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

            # ✅ Redirigir inmediatamente para evitar reenvíos o tokens antiguos
            return redirect("dashboard:dashboard")

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
            # ✅ Cambia la contraseña y mantiene la sesión activa
            request.user.set_password(nueva)
            request.user.save()
            update_session_auth_hash(request, request.user)

            success_msg = "✅ Contraseña cambiada correctamente."

            # 📨 Envío del correo de confirmación (diseño corporativo Inntesec)
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

    # ✅ Limpieza de mensajes antiguos (por accesibilidad)
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

