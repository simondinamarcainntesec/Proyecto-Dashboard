from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from tenants.models import Client
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.utils import timezone

User = get_user_model()

def tenant_login_view(request):
    if request.method == "POST":
        identifier = request.POST.get("username")  # puede ser email o username
        password = request.POST.get("password")

        if not identifier or not password:
            messages.error(request, "Debes ingresar tu correo o usuario y contraseña.")
            return render(request, "auth/login.html", {"now": timezone.now()})

        # Cerrar sesión anterior (por si existía otra empresa activa)
        if request.user.is_authenticated:
            logout(request)

        try:
            # Buscar usuario por email o username
            user = (
                User.objects.filter(Q(email__iexact=identifier) | Q(username__iexact=identifier))
                .select_related("tenant")
                .first()
            )

            if not user:
                messages.error(request, "Usuario no encontrado.")
                return render(request, "auth/login.html", {"now": timezone.now()})

            # Autenticar con ORM (evita inyecciones SQL)
            user_auth = authenticate(request, username=user.username, password=password)

            if user_auth is not None:
                login(request, user_auth)

                # ✅ Guardar tenant en sesión para el middleware
                tenant = getattr(user_auth, "tenant", None)
                if tenant:
                    request.session["tenant_id"] = tenant.id
                    request.session["tenant_name"] = tenant.name
                    messages.success(request, f"Bienvenido a {tenant.name}")
                else:
                    request.session["tenant_id"] = None
                    request.session["tenant_name"] = None
                    messages.warning(request, "Inicio de sesión sin tenant asociado.")

                return redirect("home")  # o la vista principal del dashboard
            else:
                messages.error(request, "Contraseña incorrecta. Intenta nuevamente.")
                return render(request, "auth/login.html", {"now": timezone.now()})

        except Exception as e:
            messages.error(request, f"Ocurrió un error: {str(e)}")
            return render(request, "auth/login.html", {"now": timezone.now()})

    return render(request, "auth/login.html", {"now": timezone.now()})
