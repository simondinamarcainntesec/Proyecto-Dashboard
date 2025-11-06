# ==========================
# 📦 IMPORTS DJANGO CORE
# ==========================
from django.shortcuts import render, redirect
from django.contrib import messages
from django.utils import timezone
from django.conf import settings
from django.db import IntegrityError

# ==========================
# 👥 AUTENTICACIÓN DJANGO
# ==========================
from django.contrib.auth import get_user_model, update_session_auth_hash
from django.contrib.auth.hashers import check_password
from django.contrib.auth.tokens import default_token_generator

# ==========================
# ✉️ EMAILS
# ==========================
from django.core.mail import send_mail
from django.template.loader import render_to_string

# ==========================
# 🔐 UTILIDADES DE TOKENS / ENCODING
# ==========================
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes

# ==========================
# ⚙️ UTILIDADES DJANGO
# ==========================
from django.utils.crypto import get_random_string

# ==========================
# 🏢 MODELOS LOCALES
# ==========================
from tenants.models import Client, Tenant

# ==========================
# 🧰 MÓDULOS PERSONALIZADOS
# ==========================
from utils.ms_email import  enviar_correo_recuperar_contrasena, enviar_correo_registro_cliente

# ==========================
# 🧩 LIBRERÍAS ESTÁNDAR
# ==========================
import re

# ==========================
# ✅ CONFIGURACIÓN DE USUARIO
# ==========================
User = get_user_model()

def registro_cliente(request):
    print("🚀 Entrando a registro_cliente()")

    if request.method == "POST":
        email = (request.POST.get("email") or "").strip().lower()
        print("📩 Email recibido del formulario:", email)

        if not email:
            messages.error(request, "Debes ingresar un correo electrónico.")
            print("⚠️ No se ingresó correo, redirigiendo...")
            return redirect("auth_registro_cliente")

        # 1️⃣ Buscar cliente existente
        cliente = Client.objects.filter(email__iexact=email).first()
        print("👤 Cliente encontrado:", cliente)

        if not cliente:
            messages.error(request, "El correo no está registrado como cliente.")
            print("❌ Cliente no encontrado, deteniendo flujo.")
            return redirect("auth_registro_cliente")

        # 2️⃣ Buscar tenant asociado
        tenant = Tenant.objects.filter(clients=cliente).first()
        print("🏢 Tenant encontrado:", tenant)

        if not tenant:
            messages.error(request, "No se encontró una empresa asociada a este cliente.")
            print("❌ Tenant no encontrado, deteniendo flujo.")
            return redirect("auth_registro_cliente")

        User = get_user_model()
        password = get_random_string(10)

        try:
            # ⚙️ Buscar si el usuario ya existe
            existing_user = User.objects.filter(email=email).first()

            if existing_user:
                print("⚠️ Usuario ya existente:", existing_user)
                messages.info(
                    request,
                    "Tu cuenta ya está registrada. Puedes iniciar sesión con tus credenciales existentes."
                )
                return redirect("login")

            # ✅ Crear usuario nuevo
            user = User.objects.create_user(
                username=email,
                email=email,
                first_name=getattr(cliente, "name", "Usuario"),
                tenant=tenant,
                password=password,
            )
            print("✅ Usuario nuevo creado:", user)

        except IntegrityError:
            messages.error(request, "Ya existe un usuario con este correo.")
            print("❌ Error de integridad: usuario ya existente.")
            return redirect("auth_registro_cliente")

        # 3️⃣ Enviar correo corporativo de bienvenida (usando Microsoft Graph API)
        url_login = "https://ia.inntesec.com/login"

        try:
            print("📬 Enviando correo a:", email)
            enviar_correo_registro_cliente(
                email_destino=email,
                nombre_usuario=user.first_name or "Usuario",
                tenant_name=tenant.name,
                password=password,
                url_login=url_login,
            )
            print("✅ Correo enviado correctamente (Graph API).")
            messages.success(
                request,
                "Tu cuenta ha sido creada. Se ha enviado un correo con tus credenciales de acceso.",
            )
        except Exception as e:
            print("❌ Error al enviar correo:", str(e))
            messages.warning(
                request,
                f"Tu cuenta ha sido creada, pero ocurrió un error al enviar el correo: {str(e)}",
            )

        return redirect("login")

    print("📭 Método no POST, renderizando formulario.")
    return render(request, "auth/registro_cliente.html")

def recuperar_contrasena(request):
    """
    Permite al usuario solicitar un enlace de recuperación de contraseña.
    Envía un correo con token seguro (usando Graph API).
    """
    # Limpia mensajes previos
    storage = messages.get_messages(request)
    for _ in storage:
        pass

    if request.method == "POST":
        email = (request.POST.get("email") or "").strip().lower()

        if not email:
            messages.error(request, "Debes ingresar tu correo electrónico.")
            return render(request, "auth/recuperar_contrasena.html", {"now": timezone.now()})

        # Buscar usuario asociado al correo
        user = User.objects.filter(email__iexact=email).first()

        if not user:
            messages.warning(request, "No existe una cuenta asociada a este correo.")
            return render(request, "auth/recuperar_contrasena.html", {"now": timezone.now()})

        # Generar token seguro
        token = default_token_generator.make_token(user)
        uid = urlsafe_base64_encode(force_bytes(user.pk))

        # Construir enlace completo para restablecer contraseña
        reset_link = f"{request.scheme}://{request.get_host()}/auth/reset/{uid}/{token}/"

        try:
            print(f"📬 Enviando correo de recuperación a: {email}")
            enviar_correo_recuperar_contrasena(
                email_destino=email,
                nombre_usuario=user.first_name or user.username,
                reset_link=reset_link,
            )
            print("✅ Correo de recuperación enviado correctamente (Graph API).")
            messages.success(request, "✅ Se ha enviado un enlace de recuperación a tu correo.")
            return redirect("login")

        except Exception as e:
            print("❌ Error al enviar correo con Graph API:", str(e))
            messages.error(request, f"Ocurrió un error al enviar el correo: {str(e)}")

    return render(request, "auth/recuperar_contrasena.html", {"now": timezone.now()})