from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.shortcuts import render, redirect
from django.contrib import messages
from django.utils.crypto import get_random_string
from django.conf import settings
from tenants.models import Client, Tenant
from django.db import IntegrityError

def registro_cliente(request):
    if request.method == "POST":
        email = request.POST.get("email")
        if not email:
            messages.error(request, "Debes ingresar un correo electrónico.")
            return redirect("auth/registro_cliente")

        # 1️⃣ Buscar cliente existente
        cliente = Client.objects.filter(email=email).first()
        if not cliente:
            messages.error(request, "El correo no está registrado como cliente.")
            return redirect("auth/registro_cliente")

        # 2️⃣ Buscar tenant asociado (campo 'clients')
        tenant = Tenant.objects.filter(clients=cliente).first()
        if not tenant:
            messages.error(request, "No se encontró una empresa asociada a este cliente.")
            return redirect("auth/registro_cliente")

        User = get_user_model()
        password = get_random_string(10)

        try:
            # 3️⃣ Crear o reutilizar usuario existente
            user, created = User.objects.get_or_create(
                username=email,
                defaults={
                    "email": email,
                    "first_name": getattr(cliente, "name", "Usuario"),
                    "tenant": tenant,
                },
            )

            # Si ya existía, actualizamos el tenant y la contraseña
            if not created:
                user.tenant = tenant
                user.set_password(password)
                user.save()
                mensaje = "Tu cuenta ha sido actualizada."
            else:
                user.set_password(password)
                user.save()
                mensaje = "Tu cuenta ha sido creada."

        except IntegrityError:
            messages.error(request, "Ya existe un usuario con este correo.")
            return redirect("auth/registro_cliente")

        # 4️⃣ Enviar correo con credenciales
        url_login = f"https://.inntesec.com/login"

        send_mail(
            subject=f"Acceso a tu cuenta en {tenant.name}",
            message=(
                f"Hola {user.first_name},\n\n"
                f"{mensaje}\n\n"
                f"Usuario: {user.email}\nContraseña: {password}\n"
                f"Accede aquí: {url_login}\n\n"
                "Por seguridad, cambia tu contraseña al iniciar sesión."
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=False,
        )

        messages.success(request, f"{mensaje} Revisa tu correo para obtener tus credenciales.")
        return redirect("login")

    return render(request, "auth/registro_cliente.html")
