from two_factor.views import SetupView

class Admin2FASetupView(SetupView):
    # Después del setup, vuelve al admin sí o sí
    success_url = "/admin/"
