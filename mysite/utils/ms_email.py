# mysite/utils/ms_email.py

import logging
import requests
from django.conf import settings
from django.utils import timezone
import pytz
from django.utils.html import escape


logger = logging.getLogger(__name__)

ZONA_CL = pytz.timezone("America/Santiago")

# ==============================================
# Obtener token OAuth2 (client_credentials)
# ==============================================
def obtener_token_ms():
    """
    Solicita un token OAuth2 de Microsoft usando client_credentials.
    """
    ms_conf = settings.OAUTH2_MICROSOFT
    data = {
        "grant_type": "client_credentials",
        "client_id": ms_conf["MS_CLIENT_ID"],
        "client_secret": ms_conf["MS_CLIENT_SECRET"],
        "scope": "https://graph.microsoft.com/.default",
    }

    logger.debug(f"🔑 Solicitando token a {ms_conf['MS_TOKEN_URL']}")
    response = requests.post(ms_conf["MS_TOKEN_URL"], data=data)

    if response.status_code != 200:
        logger.error(f"❌ Error obteniendo token: {response.text}")
        raise Exception(f"Error obteniendo token de Microsoft: {response.text}")

    token = response.json().get("access_token")
    logger.info("🟢 Token Microsoft Graph obtenido correctamente.")
    return token


# ==============================================
# Envío genérico de correos por Microsoft Graph
# ==============================================
def enviar_correo_ms(destinatario, asunto, cuerpo_html):
    """
    Envía correo HTML a través de Microsoft Graph API.
    """
    token = obtener_token_ms()
    remitente = settings.OAUTH2_MICROSOFT["MS_USER_EMAIL"]

    url = f"https://graph.microsoft.com/v1.0/users/{remitente}/sendMail"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    data = {
        "message": {
            "subject": asunto,
            "body": {"contentType": "HTML", "content": cuerpo_html},
            "toRecipients": [{"emailAddress": {"address": destinatario}}],
        },
        "saveToSentItems": "true",
    }

    response = requests.post(url, headers=headers, json=data)

    if response.status_code not in (200, 202):
        logger.error(f"❌ Error enviando correo: {response.status_code} {response.text}")
        raise Exception(f"Error enviando correo: {response.text}")

    logger.info(f"📬 Correo enviado correctamente a {destinatario}")


# ==============================================
# Correo específico: cambio de contraseña
# ==============================================
def enviar_correo_cambio_contrasena(email_destino, nombre_usuario):
    """Envía un correo de confirmación de cambio de contraseña con el mismo diseño corporativo."""

    asunto = "Confirmación de cambio de contraseña – Portal Clientes Inntesec"
    fecha = timezone.localtime(timezone.now(), ZONA_CL).strftime("%d/%m/%Y %H:%M:%S")

    cuerpo_html = f"""
    <html>
    <body style="font-family: Arial, sans-serif; background-color: #f4f6f8; padding: 40px; color: #333;">
      <div style="max-width: 600px; margin: auto; background: white; border-radius: 10px; padding: 30px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
        
        <div style="text-align: center; margin-bottom: 25px;">
          <img src="https://ia.inntesec.com/static/img/inntesec_logo_negro.png" alt="Inntesec" style="height: 50px;">
        </div>

        <h2 style="color: #0a0a0a;">Hola, {nombre_usuario}</h2>
        <p>Te informamos que tu contraseña fue cambiada exitosamente el <b>{fecha}</b>.</p>

        <p>Si realizaste este cambio, no necesitas hacer nada más.</p>

        <p style="color: red; margin-top: 20px;">
          Si <b>no reconoces</b> este cambio, por favor contacta inmediatamente con el equipo de administración de Inntesec:
        </p>
        <p>
          <a href="mailto:soporte@inntesec.com">soporte@inntesec.com</a>
        </p>

        <hr style="margin: 30px 0; border: none; border-top: 1px solid #ddd;">

        <p style="font-size: 12px; color: gray; text-align: center;">
          Este correo se envió automáticamente desde <b>Inntesec Agent IA</b>. Por favor, no respondas a este mensaje.
        </p>
      </div>
    </body>
    </html>
    """

    enviar_correo_ms(email_destino, asunto, cuerpo_html)


def enviar_correo_recuperar_contrasena(email_destino, nombre_usuario, reset_link):
    """Envía un correo HTML con el enlace de recuperación de contraseña (usando Graph API)."""

    asunto = "Recuperación de contraseña – Portal Clientes Inntesec"
    fecha = timezone.localtime(timezone.now(), ZONA_CL).strftime("%d/%m/%Y %H:%M:%S")

    cuerpo_html = f"""
    <html>
    <body style="font-family: Arial, sans-serif; background-color: #f4f6f8; padding: 40px; color: #333;">
      <div style="max-width: 600px; margin: auto; background: white; border-radius: 10px; padding: 30px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
        
        <div style="text-align: center; margin-bottom: 25px;">
          <img src="https://ia.inntesec.com/static/img/inntesec_logo_negro.png" alt="Inntesec" style="height: 50px;">
        </div>

        <h2 style="color: #0a0a0a;">Hola, {nombre_usuario}</h2>
        <p>Hemos recibido una solicitud para restablecer tu contraseña el <b>{fecha}</b>.</p>

        <p style="margin-top: 20px;">Para crear una nueva contraseña, haz clic en el siguiente enlace:</p>

        <p style="text-align: center; margin: 30px 0;">
          <a href="{reset_link}" target="_blank" 
            style="background-color: #007bff; color: white; text-decoration: none; padding: 12px 24px; border-radius: 6px; font-weight: bold;">
            Restablecer Contraseña
          </a>
        </p>

        <p style="color: #555;">Si <b>no realizaste</b> esta solicitud, puedes ignorar este correo.</p>

        <hr style="margin: 30px 0; border: none; border-top: 1px solid #ddd;">

        <p style="font-size: 12px; color: gray; text-align: center;">
          Este correo se envió automáticamente desde <b>Inntesec Agent IA</b>. Por favor, no respondas a este mensaje.
        </p>
      </div>
    </body>
    </html>
    """

    enviar_correo_ms(email_destino, asunto, cuerpo_html)


def enviar_correo_registro_cliente(email_destino, nombre_usuario, tenant_name, password, url_login):
    """Envía el correo de bienvenida al nuevo cliente con diseño corporativo."""
    asunto = f"Acceso a tu cuenta en {tenant_name}"

    cuerpo_html = f"""
    <html>
    <body style="font-family: Arial, sans-serif; background-color: #f4f6f8; padding: 40px; color: #333;">
      <div style="max-width: 600px; margin: auto; background: white; border-radius: 10px; padding: 30px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">

        <div style="text-align: center; margin-bottom: 25px;">
          <img src="https://ia.inntesec.com/static/img/inntesec_logo_negro.png" alt="Inntesec" style="height: 50px;">
        </div>

        <h2 style="color: #0a0a0a;">Hola, {nombre_usuario}</h2>
        <p>Tu cuenta ha sido creada exitosamente en <b>{tenant_name}</b>.</p>

        <div style="background: #f1f5ff; padding: 15px; border-radius: 8px; margin: 20px 0;">
          <p style="margin: 0;">
            <b>Usuario:</b> {email_destino}<br>
            <b>Contraseña temporal:</b> {password}
          </p>
        </div>

        <p>Puedes acceder a tu cuenta haciendo clic en el siguiente enlace:</p>
        <p style="text-align: center; margin: 25px 0;">
          <a href="{url_login}" target="_blank"
             style="background-color: #007bff; color: white; text-decoration: none; padding: 12px 24px; border-radius: 6px; font-weight: bold;">
             Iniciar Sesión
          </a>
        </p>

        <p>Por seguridad, cambia tu contraseña al iniciar sesión.</p>

        <hr style="margin: 30px 0; border: none; border-top: 1px solid #ddd;">
        <p style="font-size: 12px; color: gray; text-align: center;">
          Este mensaje fue generado automáticamente por el sistema <b>Inntesec IA</b>. Por favor, no respondas a este correo.
        </p>
      </div>
    </body>
    </html>
    """

    enviar_correo_ms(email_destino, asunto, cuerpo_html)



def _full_name(u):
    if not u:
        return "—"
    full = (f"{getattr(u, 'first_name', '') or ''} {getattr(u, 'last_name', '') or ''}").strip()
    return full or getattr(u, "username", "—") or "—"

def _html(txt: str) -> str:
    s = (txt or "").strip()
    if not s:
        return "—"
    return escape(s).replace("\n", "<br>")

def enviar_correo_ticket_asignado(ticket) -> bool:
    try:
        assigned = getattr(ticket, "assigned_to", None)
        if not assigned or not getattr(assigned, "email", ""):
            logger.warning(
                "[SOAR_TICKETS] Ticket %s sin email de asignado, no se envía correo.",
                getattr(ticket, "id", None),
            )
            return False

        tenant_name = (getattr(getattr(ticket, "tenant", None), "name", "") or "").strip() or "—"
        ticket_code = f"TICKET-{int(ticket.id):04d}" if getattr(ticket, "id", None) else "TICKET-—"

        created_dt = getattr(ticket, "opened_at", None) or timezone.now()
        created_dt_str = timezone.localtime(created_dt, ZONA_CL).strftime("%d/%m/%Y %H:%M:%S")

        due_date = getattr(ticket, "due_date", None)
        due_str = due_date.strftime("%d/%m/%Y") if due_date else "—"

        created_by = _full_name(getattr(ticket, "created_by", None))
        assigned_name = _full_name(assigned)

        alarm_id = (getattr(ticket, "alarm_id", "") or "").strip() or "—"
        dispositivo = (getattr(ticket, "dispositivo", "") or "").strip() or "—"
        tipo_amenaza = (getattr(ticket, "tipo_de_amenaza", "") or "").strip() or "—"
        severidad = (getattr(ticket, "nivel_de_severidad", "") or "").strip() or "—"

        riesgo_detectado = (
            (getattr(ticket, "descripcion_incidente", None) or "").strip()
            or (getattr(ticket, "riesgo_detectado", None) or "").strip()
            or "—"
        )
        clasificacion = (getattr(ticket, "analisis_criticidad", "") or "").strip() or "—"
        acciones = (getattr(ticket, "medidas_correctivas", "") or "").strip() or "—"
        application = (getattr(ticket, "application", "") or "").strip()

        # Fecha/Hora evento (opcional)
        event_date = getattr(ticket, "event_date", None)
        event_time = getattr(ticket, "event_time", None)
        event_dt_str = "—"
        try:
            if event_date and event_time:
                event_dt_str = f"{event_date.strftime('%d/%m/%Y')} {event_time.strftime('%H:%M:%S')}"
            elif event_date:
                event_dt_str = event_date.strftime("%d/%m/%Y")
        except Exception:
            event_dt_str = "—"

        asunto = f"Asignación de ticket SOAR — {ticket_code}"

        # ===== Helpers de “tarjeta” consistentes =====
        card_wrap_style = (
            "border:1px solid #e6e6e6;"
            "border-radius:10px;"
            "padding:14px 16px;"
            "background:#ffffff;"
        )

        soft_card_style = (
            "background:#f1f5ff;"
            "border-radius:10px;"
            "padding:16px;"
        )

        section_title_style = (
            "margin:0 0 8px;"
            "font-size:12px;"
            "font-weight:800;"
            "letter-spacing:.3px;"
            "text-transform:uppercase;"
            "color:#0a0a0a;"
        )

        section_body_style = (
            "margin:0;"
            "color:#111827;"
            "font-size:14px;"
            "line-height:1.65;"
        )

        def section_card(title: str, body_html: str) -> str:
            return f"""
              <div style="{card_wrap_style} margin-top:12px;">
                <div style="{section_title_style}">{_html(title)}</div>
                <p style="{section_body_style}">{body_html}</p>
              </div>
            """

        cuerpo_html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; background-color:#f4f6f8; padding:40px; color:#111827;">
          <div style="max-width:720px; margin:auto; background:#ffffff; border-radius:12px; padding:30px; box-shadow:0 2px 10px rgba(0,0,0,0.08);">

            <div style="text-align:center; margin-bottom:18px;">
              <img src="https://ia.inntesec.com/static/img/inntesec_logo_negro.png" alt="Inntesec" style="height:46px;">
            </div>

            <h2 style="color:#0a0a0a; margin:0 0 6px; font-size:22px; font-weight:800;">
              Se te ha asignado un ticket
            </h2>

            <p style="margin:0 0 16px; color:#374151; font-size:14px; line-height:1.6;">
              Hola, <b>{_html(assigned_name)}</b>. Se te ha asignado un evento como ticket en el módulo SOAR.
            </p>

            <!-- Tarjeta resumen (igual al estilo que ya tenías) -->
            <div style="{soft_card_style} margin:18px 0;">
              <p style="margin:0; color:#111827; font-size:14px; line-height:1.75;">
                <b>Ticket:</b> {_html(ticket_code)}<br>
                <b>Tenant:</b> {_html(tenant_name)}<br>
                <b>Fecha de creación:</b> {_html(created_dt_str)}<br>
                <b>Fecha de término (vencimiento):</b> {_html(due_str)}<br>
                <b>Creado por:</b> {_html(created_by)}<br>
              </p>
            </div>

            <h3 style="margin:18px 0 10px; color:#0a0a0a; font-size:16px; font-weight:800;">
              Detalle del evento
            </h3>

            <div style="{card_wrap_style}">
              <p style="margin:0; color:#111827; font-size:14px; line-height:1.75;">
                <b>Alarma ID:</b> {_html(alarm_id)}<br>
                <b>Dispositivo:</b> {_html(dispositivo)}<br>
                <b>Tipo de amenaza:</b> {_html(tipo_amenaza)}<br>
                <b>Severidad:</b> {_html(severidad)}<br>
                <b>Fecha/Hora evento:</b> {_html(event_dt_str)}<br>
              </p>
            </div>

            <!-- ✅ Bloques nuevos, ahora con el MISMO “feeling” -->
            {section_card("Riesgo detectado", _html(riesgo_detectado))}
            {section_card("Clasificación", _html(clasificacion))}
            {section_card("Acciones recomendadas", _html(acciones))}
            {section_card("Application", _html(application)) if application else ""}

            <hr style="margin:24px 0; border:none; border-top:1px solid #e5e7eb;">

            <p style="font-size:12px; color:#6b7280; text-align:center; margin:0; line-height:1.5;">
              Este correo se envió automáticamente desde <b>Inntesec Agent IA</b>. Por favor, no respondas a este mensaje.
            </p>
          </div>
        </body>
        </html>
        """

        enviar_correo_ms(assigned.email, asunto, cuerpo_html)
        logger.info("[SOAR_TICKETS] Correo de asignación enviado a %s para ticket %s", assigned.email, ticket_code)
        return True

    except Exception as e:
        logger.exception("[SOAR_TICKETS] Error enviando correo de asignación: %s", e)
        return False
