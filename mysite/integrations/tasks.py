from celery import shared_task
import subprocess
import os
from datetime import datetime
import pytz

@shared_task
def tarea_obtener_token():
    count_file = "celery_run_count.txt"
    log_file = "celery_run_log.txt"

    # Obtener número de ejecución
    if os.path.exists(count_file):
        with open(count_file, "r") as f:
            count = int(f.read().strip()) + 1
    else:
        count = 1
    with open(count_file, "w") as f:
        f.write(str(count))

    # Obtener hora local de Chile
    tz = pytz.timezone("America/Santiago")
    now = datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")

    try:
        # Ruta absoluta del script obtener_token.py
        script_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../obtener_token.py"))
        result = subprocess.run(
            ["python3", script_path],
            capture_output=True,
            text=True
        )

        with open(log_file, "a") as log:
            log.write(f"=== Ejecución #{count} ({now}) ===\n")
            if result.returncode == 0:
                log.write(f"✅ Ejecución correcta\n{result.stdout}\n\n")
            else:
                log.write(f"❌ Error al ejecutar script\n{result.stderr}\n\n")

    except Exception as e:
        with open(log_file, "a") as log:
            log.write(f"=== Ejecución #{count} ({now}) ===\n")
            log.write(f"❌ Excepción: {str(e)}\n\n")
