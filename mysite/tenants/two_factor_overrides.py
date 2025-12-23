# tenants/two_factor_overrides.py
from urllib.parse import urlencode

from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from two_factor.views.core import SetupView


class AdminSetupView(SetupView):
    """
    Igual que SetupView, pero cuando termina (device guardado),
    redirige SIEMPRE a la pantalla "complete" para mostrar el OK.
    """
    def done(self, form_list, **kwargs):
        # Ejecuta el flujo normal (aquí se crea/guarda el dispositivo)
        super().done(form_list, **kwargs)

        # A dónde volver después del OK
        next_url = (
            self.request.GET.get("next")
            or self.request.POST.get("next")
            or "/admin/"
        )

        qs = urlencode({"next": next_url})
        return redirect(f"/account/two_factor/setup/complete/?{qs}")


@login_required
def admin_setup_complete(request):
    """
    Pantalla intermedia: muestra el OK, y al presionar OK redirige al admin.
    """
    next_url = request.GET.get("next") or "/admin/"
    return render(request, "two_factor/core/setup_complete.html", {"next": next_url})
