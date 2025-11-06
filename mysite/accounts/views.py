from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.shortcuts import render, redirect
from django.contrib import messages
from django.utils.crypto import get_random_string
from django.conf import settings
from tenants.models import Client, Tenant
from django.db import IntegrityError
from utils.ms_email import enviar_correo_ms

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
            user, created = User.objects.get_or_create(
                username=email,
                defaults={
                    "email": email,
                    "first_name": getattr(cliente, "name", "Usuario"),
                    "tenant": tenant,
                },
            )

            if created:
                mensaje = "Tu cuenta ha sido creada."
                print("✅ Usuario nuevo creado:", user)
            else:
                mensaje = "Tu cuenta ha sido actualizada."
                user.tenant = tenant
                print("♻️ Usuario existente, actualizado:", user)

            user.set_password(password)
            user.save()
            print("🔐 Contraseña generada:", password)

        except IntegrityError:
            messages.error(request, "Ya existe un usuario con este correo.")
            print("❌ Error de integridad: usuario ya existente.")
            return redirect("auth_registro_cliente")

        # 3️⃣ Construir correo HTML
        url_login = "https://ia.inntesec.com/login"
        asunto = f"Acceso a tu cuenta en {tenant.name}"
        cuerpo_html = f"""
        <html>
        <body style="font-family: Arial, sans-serif;">
            <h2>Hola, {user.first_name}</h2>
            <p>{mensaje}</p>
            <p>
                <b>Usuario:</b> {user.email}<br>
                <b>Contraseña:</b> {password}
            </p>
            <p>
                Puedes acceder a tu cuenta haciendo clic aquí:<br>
                <a href="{url_login}" target="_blank">{url_login}</a>
            </p>
            <p>Por seguridad, cambia tu contraseña al iniciar sesión.</p>
            <hr>
            <p style="font-size: 12px; color: #777;">
                Este mensaje fue generado automáticamente por el sistema Inntesec IA.
            </p>
        </body>
        </html>
        """

        # 4️⃣ Intentar enviar correo
        try:
            print("📬 Enviando correo a:", email)
            enviar_correo_ms(
                destinatario=email,
                asunto=asunto,
                cuerpo_html=cuerpo_html,
            )
            print("✅ Correo enviado correctamente (Graph API).")
            messages.success(
                request,
                f"{mensaje} Se ha enviado un correo con tus credenciales de acceso.",
            )
        except Exception as e:
            print("❌ Error al enviar correo:", str(e))
            messages.warning(
                request,
                f"{mensaje} Pero ocurrió un error al enviar el correo: {str(e)}",
            )

        return redirect("login")

    print("📭 Método no POST, renderizando formulario.")
    return render(request, "auth/registro_cliente.html")