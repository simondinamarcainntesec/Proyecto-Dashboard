from tenants.models import Tenant


def get_active_tenant(request):
    """
    Tenant activo:
    - Si NO es Inntesec: siempre su tenant fijo (request.user.tenant)
    - Si es Inntesec: usa request.tenant si existe; si no, usa sesión tenant_id (de tu switch_tenant)
    - Fallback: request.user.tenant
    """
    # 1) Si tu middleware ya setea request.tenant, úsalo
    t = getattr(request, "tenant", None)
    if t:
        user_tenant = getattr(request.user, "tenant", None)
        if user_tenant and user_tenant.name and user_tenant.name.lower() != "inntesec":
            return user_tenant
        return t

    # 2) Tenant real del usuario (si no es inntesec, no se permite cambiar)
    user_tenant = getattr(request.user, "tenant", None)
    if user_tenant and user_tenant.name and user_tenant.name.lower() != "inntesec":
        return user_tenant

    # 3) Si es Inntesec, puede usar tenant_id de sesión
    tid = request.session.get("tenant_id")
    if tid:
        try:
            return Tenant.objects.get(id=tid)
        except Tenant.DoesNotExist:
            return user_tenant

    # 4) Fallback
    return user_tenant
