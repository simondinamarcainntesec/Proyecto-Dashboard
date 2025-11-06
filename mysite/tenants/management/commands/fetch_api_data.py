import requests
from django.core.management.base import BaseCommand
from django.db import transaction, IntegrityError
from tenants.models import Tenant, Client
import logging
from django.conf import settings
import os

logger = logging.getLogger(__name__)

# === URLs ===
TENANTS_API_URL = "https://iaproductivo.inntesec.cl/webhook/4721cd5e-0c36-4773-8292-fa3b8580cebd"
CLIENTS_API_URL = "https://iaproductivo.inntesec.cl/webhook/4721cd5e-0c36-4773-8292-fa3b8580cebd"

# === Autenticación y parámetros ===
API_PASSKEY = "@aDv%6rSBPXXhD*iW7dl6PCjOZ4a0Fkc"
API_PARAM_NAME = "value"
API_PARAM_VALUE_TENANTS = "Empresa"
API_PARAM_VALUE_CLIENTS = "Clientes"


# --- Helper para convertir a entero de forma segura ---
def safe_int(value):
    if value is None:
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


class Command(BaseCommand):
    help = "Obtiene datos de empresas y clientes desde la API y los guarda en la BD."

    def handle(self, *args, **options):
        self.stdout.write("Iniciando la obtención de datos desde la API...")

        api_headers = {"passkey": API_PASSKEY}
        api_params_tenants = {API_PARAM_NAME: API_PARAM_VALUE_TENANTS}
        api_params_clients = {API_PARAM_NAME: API_PARAM_VALUE_CLIENTS}

        try:
            # === Obtener Tenants ===
            self.stdout.write(f"Obteniendo empresas desde {TENANTS_API_URL}...")
            response_tenants = requests.get(
                TENANTS_API_URL,
                headers=api_headers,
                params=api_params_tenants,
                timeout=30,
            )
            response_tenants.raise_for_status()
            tenants_data = response_tenants.json()
            self.stdout.write(f"Recibidas {len(tenants_data)} entradas de empresas.")

            tenants_creados = 0
            tenants_actualizados = 0
            processed_tenant_names = set()

            with transaction.atomic():
                for tenant_api_data in tenants_data:
                    tenant_name = tenant_api_data.get("Empresa")
                    if not tenant_name:
                        self.stderr.write(
                            f"Registro de empresa omitido por falta de nombre ('Empresa'): {tenant_api_data}"
                        )
                        continue

                    tenant_name_clean = tenant_name.strip()
                    if tenant_name_clean in processed_tenant_names:
                        continue
                    processed_tenant_names.add(tenant_name_clean)

                    try:
                        tenant, created = Tenant.objects.update_or_create(
                            name__iexact=tenant_name_clean,
                            defaults={
                                "name": tenant_name_clean,
                                "alarms_one_id": safe_int(tenant_api_data.get("AlarmsOne")),
                                "logs360siem_id": safe_int(tenant_api_data.get("Logs360SIEM")),
                                "site24x7_id": safe_int(tenant_api_data.get("Site24x7")),
                            },
                        )

                        if created:
                            tenants_creados += 1
                        else:
                            tenants_actualizados += 1
                    except IntegrityError as e:
                        self.stderr.write(f"Error de integridad al procesar empresa {tenant_name_clean}: {e}")
                    except Exception as e:
                        self.stderr.write(f"Error inesperado al procesar empresa {tenant_name_clean}: {e}")

            self.stdout.write(
                self.style.SUCCESS(
                    f"Empresas procesadas: {tenants_creados} creadas, {tenants_actualizados} actualizadas."
                )
            )

            # === Obtener Clientes ===
            self.stdout.write(f"Obteniendo clientes desde {CLIENTS_API_URL}...")
            response_clients = requests.get(
                CLIENTS_API_URL,
                headers=api_headers,
                params=api_params_clients,
                timeout=30,
            )
            response_clients.raise_for_status()
            clients_data = response_clients.json()
            self.stdout.write(f"Recibidas {len(clients_data)} entradas de clientes.")

            clients_creados = 0
            clients_actualizados = 0
            processed_client_api_ids = set()

            with transaction.atomic():
                for client_api_data in clients_data:
                    api_id = safe_int(client_api_data.get("N"))
                    client_email = client_api_data.get("Email")
                    tenant_name_from_client = client_api_data.get("Empresa")

                    if api_id is None:
                        self.stderr.write(f"Omitido por falta de ID ('N'): {client_api_data}")
                        continue
                    if not client_email:
                        self.stderr.write(f"Omitido por falta de Email: {client_api_data}")
                        continue

                    # Evita procesar dos veces el mismo ID
                    if api_id in processed_client_api_ids:
                        continue
                    processed_client_api_ids.add(api_id)

                    # === Buscar o crear Tenant ===
                    tenant_obj = None
                    if tenant_name_from_client:
                        tenant_name_clean = tenant_name_from_client.strip()
                        try:
                            tenant_obj = Tenant.objects.filter(name__iexact=tenant_name_clean).first()

                            # Si no existe, crearla automáticamente
                            if not tenant_obj:
                                tenant_obj = Tenant.objects.create(
                                    name=tenant_name_clean,
                                    alarms_one_id=safe_int(client_api_data.get("AlarmsOne")),
                                    logs360siem_id=safe_int(client_api_data.get("Logs360SIEM")),
                                    site24x7_id=safe_int(client_api_data.get("Site24x7")),
                                )
                                self.stdout.write(
                                    f"✅ Empresa '{tenant_name_clean}' creada automáticamente para cliente {api_id}."
                                )
                        except Exception as e:
                            self.stderr.write(
                                f"⚠️ Error al obtener o crear empresa '{tenant_name_clean}' para cliente {api_id}: {e}"
                            )
                    else:
                        self.stderr.write(
                            f"Cliente {api_id} ({client_email}): No tiene empresa asociada. Omitiendo."
                        )
                        continue

                    # === Crear o actualizar cliente (permitiendo emails duplicados) ===
                    try:
                        client, created = Client.objects.update_or_create(
                            api_id=api_id,
                            defaults={
                                "tenant": tenant_obj,
                                "name": client_api_data.get("Nombre", ""),
                                "email": client_email,
                                "phone": client_api_data.get("Telefono"),
                                "telegram_id": client_api_data.get("Telegram"),
                            },
                        )

                        if created:
                            clients_creados += 1
                        else:
                            clients_actualizados += 1
                    except Exception as e:
                        self.stderr.write(
                            f"Error inesperado al procesar cliente {api_id} ({client_email}): {e}"
                        )

            self.stdout.write(
                self.style.SUCCESS(
                    f"Clientes procesados: {clients_creados} creados, {clients_actualizados} actualizados."
                )
            )

            self.stdout.write(self.style.SUCCESS("✅ Proceso completado con éxito."))

        except requests.exceptions.HTTPError as e:
            self.stderr.write(
                self.style.ERROR(f"Error HTTP {e.response.status_code} al llamar a la API: {e}")
            )
            try:
                self.stderr.write(f"Respuesta de la API: {e.response.text}")
            except Exception:
                pass
            logger.exception("Error HTTP al llamar a la API")

        except requests.exceptions.RequestException as e:
            self.stderr.write(self.style.ERROR(f"Error de conexión con la API: {e}"))
            logger.exception("Error de conexión con la API")

        except Exception as e:
            self.stderr.write(
                self.style.ERROR(f"Error inesperado durante la ingesta: {type(e).__name__} - {e}")
            )
            logger.exception("Error inesperado durante la ingesta")
