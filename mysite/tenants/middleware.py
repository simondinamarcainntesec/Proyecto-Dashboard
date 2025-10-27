from tenants.models import Tenant

class ActiveTenantMiddleware:
    """
    Carga el tenant actual en cada request según la sesión.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        tenant_id = request.session.get("tenant_id")
        request.tenant = None
        if tenant_id:
            try:
                request.tenant = Tenant.objects.get(id=tenant_id)
            except Tenant.DoesNotExist:
                request.tenant = None
        return self.get_response(request)
