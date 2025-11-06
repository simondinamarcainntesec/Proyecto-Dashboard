from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tenants', '0003_alter_tenantuser_alarma_correo_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='tenantuser',
            name='Alarma_Telefono',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='tenantuser',
            name='Alarma_Correo',
            field=models.BooleanField(default=False),
        ),
    ]
