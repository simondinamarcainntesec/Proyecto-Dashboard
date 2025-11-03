from django.db import models

# Create your models here.
from django.db import models

class IncidenteSOAR(models.Model):
    # OJO: asumo que alarmd_id es único y sirve como PK. Si no, dime y ajustamos.
    alarmd_id = models.CharField(primary_key=True, max_length=255, db_column='alarmd_id')

    aotag = models.CharField(max_length=255, null=True, blank=True, db_column='aotag')
    dispositivo = models.CharField(max_length=255, null=True, blank=True, db_column='dispositivo')
    descripcion_incidente = models.TextField(null=True, blank=True, db_column='descripcion_incidente')
    tipo_de_amenaza = models.CharField(max_length=255, null=True, blank=True, db_column='tipo_de_amenaza')
    nivel_de_severidad = models.CharField(max_length=255, null=True, blank=True, db_column='nivel_de_severidad')
    medidas_correctivas = models.TextField(null=True, blank=True, db_column='medidas_correctivas')
    resumen_humano = models.TextField(null=True, blank=True, db_column='resumen_humano')

    # Mantengo exactamente el nombre que nos diste (parece que “riego” es un typo de “riesgo”,
    # pero apunto a la columna tal cual)
    riego_detectado = models.CharField(max_length=255, null=True, blank=True, db_column='riego_detectado')
    analisis_criticidad = models.TextField(null=True, blank=True, db_column='analisis_criticidad')

    # En Postgres el “ícono de reloj” suele ser DATE y TIME.
    date = models.DateField(null=True, blank=True, db_column='date')
    time = models.TimeField(null=True, blank=True, db_column='time')

    # Columna con mayúscula
    application = models.CharField(max_length=255, null=True, blank=True, db_column='Application')

    class Meta:
        managed = False  # ¡Muy importante!
        # Esquema + tabla. Con Postgres puedes usar el nombre calificado con comillas escapadas:
        db_table = 'agent"."incidentes_soar'  # Django lo citará como "agent"."incidentes_soar"
        # Alternativa si tu search_path ya incluye agent:
        # db_table = 'incidentes_soar'

    def __str__(self):
        return f"{self.alarmd_id} - {self.nivel_de_severidad or ''}"
