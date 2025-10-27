from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages
from tenants.models import Tenant

def tenant_required(view_func):
    """
    Decorador que asegura que el usuario esté autenticado
    y que tenga un tenant válido asociado en la sesión.
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.error(request, "Debes iniciar sesión primero.")
            return redirect("auth/login.html")

        tenant_id = request.session.get("tenant_id")
        if not tenant_id:
            messages.error(request, "No se pudo determinar tu empresa (tenant).")
            return redirect("auth/login.html")

        try:
            tenant = Tenant.objects.get(id=tenant_id)
        except Tenant.DoesNotExist:
            messages.error(request, "El tenant asociado no existe o fue eliminado.")
            return redirect("auth/login.html")

        # Asignamos el tenant a la request para usarlo en la vista
        request.tenant = tenant
        return view_func(request, *args, **kwargs)
    return _wrapped_view
