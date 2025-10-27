from django.contrib.auth.backends import ModelBackend
from tenants.models import TenantUser

class TenantBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        tenant_name = kwargs.get("tenant_name") or request.POST.get("tenant")
        if not tenant_name:
            return None
        try:
            user = TenantUser.objects.get(username=username, tenant__name__iexact=tenant_name)
        except TenantUser.DoesNotExist:
            return None

        if user.check_password(password):
            return user
        return None
