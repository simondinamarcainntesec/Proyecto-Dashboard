# home/migrations/00YY_drop_whitelist_pref_user_id_agent_schema.py
from django.db import migrations


def _drop_user_id_column(apps, schema_editor):
    """
    Elimina la columna user_id en el esquema agent, si existe.
    No depende del estado del modelo (evita KeyError/RemoveField).
    """
    # Ajusta este nombre si tu tabla se llama distinto en DB
    table_name = "whitelist_country_preference"  # <- el nombre real de la tabla en agent

    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            f'ALTER TABLE "agent"."{table_name}" DROP COLUMN IF EXISTS "user_id";'
        )


class Migration(migrations.Migration):

    dependencies = [
        ("home", "0003_whitelistcountrypreference"),  # <-- pon aquí tu última migración real
    ]

    operations = [
        migrations.RunPython(_drop_user_id_column, reverse_code=migrations.RunPython.noop),
    ]
