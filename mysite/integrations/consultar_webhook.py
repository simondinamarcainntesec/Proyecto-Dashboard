import os
import sys
import django
import requests
from django.utils import timezone

# === Configuración Django ===
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mysite.settings")
django.setup()

from tenants.models import Tenant, Client

# === Configuración del Webhook ===
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "").strip()
PASSKEY = os.getenv("PASSKEY", "").strip()
PARAMS = {"value": "crear_ticket"}


def sync_clients():
    headers = {"passkey": PASSKEY}

    try:
        print("🌐 Consultando webhook...")
        response = requests.get(WEBHOOK_URL, headers=headers, params=PARAMS)
        response.raise_for_status()
        data = response.json()
        print(f"✅ Webhook consultado correctamente ({len(data)} registros recibidos)\n")

    except requests.exceptions.RequestException as e:
        print(f"❌ Error al consultar el webhook: {e}")
        return

    total_insertados = 0
    total_actualizados = 0
    total_omitidos = 0

    for item in data:
        empresa = item.get("Empresa")
        email = item.get("Email")
        id_externo = item.get("Id")

        if not empresa or not email or not id_externo:
            print(f"⚠️ Omitido: registro sin Empresa, Email o Id → {item}")
            total_omitidos += 1
            continue

        tenant = Tenant.objects.filter(name=empresa).first()
        if not tenant:
            print(f"⚠️ Empresa no encontrada: {empresa} → omitido")
            total_omitidos += 1
            continue

        client, created = Client.objects.update_or_create(
            id=id_externo,
            defaults={
                "name": item.get("Nombre"),
                "email": email,
                "phone": item.get("Telefono"),
                "tenant": tenant,
                "updated_at": timezone.now(),
            }
        )

        if created:
            client.created_at = timezone.now()
            client.save(update_fields=["created_at"])
            print(f"🟢 Insertado → ID {id_externo} | {email} | Empresa: {empresa}")
            total_insertados += 1
        else:
            print(f"🟡 Actualizado → ID {id_externo} | {email} | Empresa: {empresa}")
            total_actualizados += 1

    print("\n📊 --- Resumen final ---")
    print(f"✅ Insertados: {total_insertados}")
    print(f"🔁 Actualizados: {total_actualizados}")
    print(f"🚫 Omitidos: {total_omitidos}")


if __name__ == "__main__":
    sync_clients()
