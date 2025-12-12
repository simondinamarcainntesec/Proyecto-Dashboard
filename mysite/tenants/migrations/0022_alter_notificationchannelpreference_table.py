from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("tenants", "0021_move_notification_pref_to_agent"),
    ]

    operations = [
        # Intencionalmente vacío: NO renombrar tabla en BD
    ]