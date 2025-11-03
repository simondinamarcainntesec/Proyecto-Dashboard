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

logger = logging.getLogger(__name__)
User = get_user_model()

# ========================== LOGIN ==========================
def tenant_login_view(request):
    """
    Login con identifier (email o username) + password.
    Opcional: POST['tenant'] para scope explícito.
    """
    if request.method == "POST":
        identifier = request.POST.get("username")
        password = request.POST.get("password")
        form_tenant_name = request.POST.get("tenant")

        if not identifier or not password:
            messages.error(request, "Debes ingresar tu correo o usuario y contraseña.")
            return render(request, "auth/login.html", {"now": timezone.now()})

        if request.user.is_authenticated:
            logout(request)

        user = None
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
                request, username=user.username, password=password, tenant_name=tenant.name
            )
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
                request, username=user.username, password=password, tenant_name=tenant_name_guess
            )
            if user_auth is None:
                user_auth = authenticate(request, username=user.username, password=password)

        if user_auth is not None:
            login(request, user_auth)
            tenant = getattr(user_auth, "tenant", None)
            if tenant:
                request.session["tenant_id"] = tenant.id
                request.session["tenant_name"] = tenant.name
                logger.info("[Login] Ok user=%s tenant=%s (guardado en sesión).",
                            user_auth.username, tenant.name)
            else:
                request.session["tenant_id"] = None
                request.session["tenant_name"] = None
                logger.warning("[Login] Usuario autenticado sin tenant asociado: %s", user_auth.username)
                messages.warning(request, "Inicio de sesión sin tenant asociado.")

            return redirect("dashboard")

        messages.error(request, "Credenciales inválidas.")
        return render(request, "auth/login.html", {"now": timezone.now()})

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
        return redirect("dashboard")

    tenant = Tenant.objects.filter(id=tenant_id).first()
    if not tenant:
        messages.error(request, "El tenant seleccionado no existe.")
        return redirect("dashboard_realtime")

    # Guardar en sesión
    request.session["tenant_id"] = tenant.id
    request.session["tenant_name"] = tenant.name
    logger.info("[SwitchTenant] %s cambió a tenant %s", request.user.username, tenant.name)

    # Determinar destino según Referer
    referer = request.META.get("HTTP_REFERER", "")
    if "realtime" in referer.lower():
        logger.debug("[SwitchTenant] Redirigiendo a dashboard_realtime tras cambio de tenant.")
        return redirect("dashboard_realtime")
    else:
        logger.debug("[SwitchTenant] Redirigiendo a dashboard histórico tras cambio de tenant.")
        return redirect("dashboard")
