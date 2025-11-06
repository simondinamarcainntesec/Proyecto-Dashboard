from django.core.mail import send_mail
from django.conf import settings

print("Probando envío con:", settings.EMAIL_HOST_USER)

send_mail(
    "Prueba Mailtrap",
    "Esto es una prueba desde Django.",
    settings.DEFAULT_FROM_EMAIL,
    ["tu_correo@ejemplo.com"],
    fail_silently=False,
)
print("✅ Envío completado")
