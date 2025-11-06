import os
import logging
from logging.handlers import RotatingFileHandler
import subprocess
from time import sleep

# =======================
# Logger rotativo
# =======================
logfile = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "celery_worker.log")
handler = RotatingFileHandler(logfile, maxBytes=5*1024*1024, backupCount=3)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)

logger = logging.getLogger("celery")
logger.addHandler(handler)
logger.setLevel(logging.INFO)

# =======================
# Contador de ejecución
# =======================
count_file = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "celery_run_count.txt")

def get_next_run_count():
    if not os.path.exists(count_file):
        count = 0
    else:
        with open(count_file, "r") as f:
            try:
                count = int(f.read().strip())
            except:
                count = 0
    count += 1
    with open(count_file, "w") as f:
        f.write(str(count))
    return count

# =======================
# Ejecutar script con backoff
# =======================
def ejecutar_script(script_path, max_retries=5):
    delay = 0.5
    for attempt in range(1, max_retries + 1):
        try:
            result = subprocess.run(
                ["python3", script_path],
                capture_output=True,
                text=True,
                check=True,
            )
            token = result.stdout.strip()
            if not token:
                raise ValueError("Token vacío")
            return token
        except Exception as e:
            logger.warning(f"Backing off ejecutar_script(...) for {delay}s (Attempt {attempt}/{max_retries}) - {e}")
            sleep(delay)
            delay *= 2  # Exponential backoff
    raise RuntimeError(f"Fallo en script después de {max_retries} intentos")
