from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tenants", "0006_remove_client_api_id_alter_client_id"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                ALTER TABLE tenants_client
                DROP COLUMN IF EXISTS api_id;
            """,
            reverse_sql="""
                ALTER TABLE tenants_client
                ADD COLUMN api_id integer;
            """,
        ),
        migrations.AlterField(
            model_name="client",
            name="id",
            field=models.IntegerField(
                primary_key=True,
                serialize=False,
                help_text="ID numérico del cliente proveniente del webhook (API externa)",
            ),
        ),
    ]
