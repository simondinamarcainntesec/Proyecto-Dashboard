import requests
from django.core.management.base import BaseCommand
from django.db import transaction, IntegrityError
# Asegúrate de importar los modelos correctos
from tenants.models import Tenant, Client
import logging
# Importa settings para obtener la passkey de forma segura
from django.conf import settings
import os # Para getenv como alternativa

logger = logging.getLogger(__name__)

# --- URLs ---
TENANTS_API_URL = "https://iaproductivo.inntesec.cl/webhook/4721cd5e-0c36-4773-8292-fa3b8580cebd"
CLIENTS_API_URL = "https://iaproductivo.inntesec.cl/webhook/4721cd5e-0c36-4773-8292-fa3b8580cebd"

# --- Autenticación y Parámetros ---
# Es MEJOR guardar esto en settings.py o variables de entorno
# API_PASSKEY = getattr(settings, 'TENANT_API_PASSKEY', 'TU_PASSKEY_POR_DEFECTO')
# API_PARAM_VALUE = getattr(settings, 'TENANT_API_PARAM_VALUE', 'valor_parametro_por_defecto')

# Alternativa directa (menos segura, pero funciona para el ejemplo):
API_PASSKEY = "@aDv%6rSBPXXhD*iW7dl6PCjOZ4a0Fkc" # <-- Reemplaza esto!
API_PARAM_NAME = "value" # <-- El nombre del parámetro que necesita tu API
API_PARAM_VALUE_TENANTS = "Empresa" # <-- El valor del parámetro para obtener empresas
API_PARAM_VALUE_CLIENTS = "Clientes" # <-- El valor del parámetro para obtener clientes (ajusta si es diferente)


# Función helper para convertir a entero de forma segura
def safe_int(value):
    if value is None:
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None

class Command(BaseCommand):
    help = 'Obtiene datos de empresas y clientes desde la API (con passkey y param) y los guarda en la BD'

    def handle(self, *args, **options):
        self.stdout.write("Iniciando la obtención de datos desde la API...")

        # --- Preparar Headers y Params ---
        api_headers = {"passkey": API_PASSKEY}
        api_params_tenants = {API_PARAM_NAME: API_PARAM_VALUE_TENANTS}
        api_params_clients = {API_PARAM_NAME: API_PARAM_VALUE_CLIENTS}


        try:
            # --- Obtener y guardar Tenants (Empresas) ---
            self.stdout.write(f"Obteniendo empresas desde {TENANTS_API_URL}...")
            response_tenants = requests.get(
                TENANTS_API_URL,
                headers=api_headers,
                params=api_params_tenants, # <-- Añadido parámetro
                timeout=30
            )
            response_tenants.raise_for_status()
            tenants_data = response_tenants.json()
            self.stdout.write(f"Recibidas {len(tenants_data)} entradas de empresas.")


            tenants_creados = 0
            tenants_actualizados = 0
            processed_tenant_names = set()

            with transaction.atomic():
                for tenant_api_data in tenants_data:
                    tenant_name = tenant_api_data.get('Empresa')
                    if not tenant_name:
                        self.stderr.write(f"Registro de empresa omitido por falta de nombre ('Empresa'): {tenant_api_data}")
                        continue

                    if tenant_name in processed_tenant_names:
                        continue
                    processed_tenant_names.add(tenant_name)

                    try:
                        tenant, created = Tenant.objects.update_or_create(
                            name=tenant_name,
                            defaults={
                                'alarms_one_value': safe_int(tenant_api_data.get('AlarmsOne')),
                                'logs360siem_value': safe_int(tenant_api_data.get('Logs360SIEM')),
                                'site24x7_value': safe_int(tenant_api_data.get('Site24x7')),
                            }
                        )
                        if created:
                            tenants_creados += 1
                        else:
                            tenants_actualizados += 1
                    except IntegrityError as e:
                         self.stderr.write(f"Error de integridad al procesar empresa {tenant_name}: {e}")
                    except Exception as e:
                         self.stderr.write(f"Error inesperado al procesar empresa {tenant_name}: {e}")

            self.stdout.write(self.style.SUCCESS(f"Empresas procesadas: {tenants_creados} creadas, {tenants_actualizados} actualizadas."))

            # --- Obtener y guardar Clientes ---
            self.stdout.write(f"Obteniendo clientes desde {CLIENTS_API_URL}...")
            response_clients = requests.get(
                CLIENTS_API_URL,
                headers=api_headers,
                params=api_params_clients, # <-- Añadido parámetro
                timeout=30
            )
            response_clients.raise_for_status()
            clients_data = response_clients.json()
            self.stdout.write(f"Recibidas {len(clients_data)} entradas de clientes.")


            clients_creados = 0
            clients_actualizados = 0
            processed_client_api_ids = set()
            processed_client_emails = set()

            with transaction.atomic():
                for client_api_data in clients_data:
                    api_id = safe_int(client_api_data.get('N'))
                    client_email = client_api_data.get('Email')
                    tenant_name_from_client = client_api_data.get('Empresa')

                    if api_id is None:
                        self.stderr.write(f"Registro de cliente omitido por falta de ID numérico ('N'): {client_api_data}")
                        continue
                    if not client_email:
                         self.stderr.write(f"Registro de cliente {api_id} omitido por falta de Email: {client_api_data}")
                         continue

                    if api_id in processed_client_api_ids or client_email.lower() in processed_client_emails:
                        continue
                    processed_client_api_ids.add(api_id)
                    processed_client_emails.add(client_email.lower())

                    tenant_obj = None
                    if tenant_name_from_client:
                        try:
                            tenant_obj = Tenant.objects.get(name=tenant_name_from_client)
                        except Tenant.DoesNotExist:
                            self.stderr.write(f"Cliente {api_id} ({client_email}): No se encontró la empresa '{tenant_name_from_client}' en la BD local. Omitiendo.")
                            continue
                        except Tenant.MultipleObjectsReturned:
                             self.stderr.write(f"Cliente {api_id} ({client_email}): Se encontraron múltiples empresas con el nombre '{tenant_name_from_client}'. Omitiendo.")
                             continue
                    elif not tenant_obj:
                         self.stderr.write(f"Cliente {api_id} ({client_email}): No se especificó empresa ('Empresa' es null) y el modelo requiere una. Omitiendo.")
                         continue

                    try:
                        client, created = Client.objects.update_or_create(
                            api_id=api_id,
                            defaults={
                                'tenant': tenant_obj,
                                'name': client_api_data.get('Nombre', ''),
                                'email': client_email,
                                'phone': client_api_data.get('Telefono'),
                                'telegram_id': client_api_data.get('Telegram'),
                            }
                        )
                        if created:
                            clients_creados += 1
                        else:
                            clients_actualizados += 1
                    except IntegrityError as e:
                        self.stderr.write(f"Error de integridad al procesar cliente {api_id} ({client_email}): {e}")
                        existing_client = Client.objects.filter(email__iexact=client_email).first()
                        if existing_client and existing_client.api_id != api_id:
                             self.stderr.write(f" -> Conflicto: Email '{client_email}' ya existe para api_id {existing_client.api_id}.")
                    except Exception as e:
                         self.stderr.write(f"Error inesperado al procesar cliente {api_id} ({client_email}): {e}")

            self.stdout.write(self.style.SUCCESS(f"Clientes procesados: {clients_creados} creados, {clients_actualizados} actualizados."))

            self.stdout.write(self.style.SUCCESS("Proceso completado con éxito."))

        except requests.exceptions.HTTPError as e:
             # Captura errores HTTP específicos para dar más detalles
             self.stderr.write(self.style.ERROR(f"Error HTTP {e.response.status_code} al llamar a la API: {e}"))
             try:
                 # Intenta mostrar la respuesta de la API si está disponible
                 self.stderr.write(f"Respuesta de la API: {e.response.text}")
             except Exception:
                 pass # No hacer nada si no se puede leer la respuesta
             logger.exception("Error HTTP al llamar a la API")
        except requests.exceptions.RequestException as e:
            self.stderr.write(self.style.ERROR(f"Error de conexión con la API: {e}"))
            logger.exception("Error de conexión con la API")
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Error inesperado durante la ingesta: {type(e).__name__} - {e}"))
            logger.exception("Error inesperado durante la ingesta")