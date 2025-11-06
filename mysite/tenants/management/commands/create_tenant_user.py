from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from tenants.models import Tenant, Client
from django.db import transaction

class Command(BaseCommand):
    help = "Crea un usuario vinculado a un tenant (empresa) específico"

    def add_arguments(self, parser):
        parser.add_argument('--email', required=True, help='Correo del usuario')
        parser.add_argument('--tenant', required=True, help='Nombre exacto del tenant')
        parser.add_argument('--password', required=True, help='Contraseña del usuario')
        parser.add_argument('--username', help='Nombre de usuario (opcional)')
        parser.add_argument('--name', help='Nombre completo del cliente (opcional)')
        parser.add_argument('--phone', help='Teléfono del cliente (opcional)')

    @transaction.atomic
    def handle(self, *args, **options):
        email = options['email'].strip().lower()
        tenant_name = options['tenant'].strip()
        password = options['password']
        username = options.get('username') or email.split('@')[0]
        name = options.get('name', username)
        phone = options.get('phone', '')

        User = get_user_model()

        try:
            tenant = Tenant.objects.get(name=tenant_name)
        except Tenant.DoesNotExist:
            raise CommandError(f"❌ No existe un tenant llamado '{tenant_name}'")

        user, created_user = User.objects.get_or_create(
            email=email,
            defaults={
                'username': username,
                'tenant': tenant,
            }
        )

        if created_user:
            user.set_password(password)
            user.save()
            self.stdout.write(self.style.SUCCESS(f"✅ Usuario '{email}' creado correctamente"))
        else:
            self.stdout.write(self.style.WARNING(f"⚠️ Usuario '{email}' ya existía, se actualizó su tenant y contraseña"))
            user.tenant = tenant
            user.set_password(password)
            user.save()

        client, created_client = Client.objects.get_or_create(
            email=email,
            defaults={
                'tenant': tenant,
                'name': name,
                'phone': phone,
                'user': user,
            }
        )

        if not created_client:
            client.user = user
            client.tenant = tenant
            client.name = name or client.name
            client.phone = phone or client.phone
            client.save()

        self.stdout.write(self.style.SUCCESS(
            f"✅ Usuario '{user.username}' vinculado correctamente al tenant '{tenant.name}' y al cliente '{client.name}'"
        ))
