This document explains how to run Celery (beat + worker) for this Django project (mysite).

Prerequisites
- Activate the project's virtualenv: `source ../venv/bin/activate` when inside `mysite/`.
- Redis running at redis://localhost:6379 (as configured in settings.py).

Quick start (development)

There are two simple ways to run Celery during development. Use the one that fits where you are starting from.

Option A — from the project root (recommended):

This is the most common workflow. Run these commands from the repository root (`/home/inntesec-ia/Proyecto-Dashboard`):

```bash
# if inside the inner mysite/ directory, the venv is one level up
source ../venv/bin/activate

# run celery pointing at the package; when run from here use the same -A mysite
pkill -f 'celery'
nohup celery -A mysite beat -l info &
nohup celery -A mysite worker -l info --concurrency=1 &
```

Notes about why commands can fail
- If Celery complains it can't find `mysite.settings` or that the module `mysite` has no attribute `celery`, it's usually because you're running from the wrong directory or PYTHONPATH isn't set. Starting from the repository root and `cd`ing into the `mysite` folder as above is the simplest fix.
- If beat fails with errors about a corrupted schedule DB, remove the `celerybeat-schedule` file in the working directory and restart:

```bash
# stop celery processes, then
rm -f celerybeat-schedule
```

- Prefer using pidfiles or a process supervisor (systemd / supervisor) in production rather than backgrounding with `&`.

Note: we moved the schedule (beat) definitions into `mysite/mysite/celery.py` so there's a single source of truth.

Systemd unit examples (production)
Create two unit files (example below) and enable them with `systemctl`.

1) /etc/systemd/system/celery-beat.service
```
[Unit]
Description=Celery Beat Service
After=network.target

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/home/inntesec-ia/Proyecto-Dashboard/mysite
EnvironmentFile=/home/inntesec-ia/Proyecto-Dashboard/.env
ExecStart=/home/inntesec-ia/Proyecto-Dashboard/venv/bin/celery -A mysite beat -l info --pidfile=/var/run/celery/beat.pid
Restart=always

[Install]
WantedBy=multi-user.target
```

2) /etc/systemd/system/celery-worker.service
```
[Unit]
Description=Celery Worker Service
After=network.target

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/home/inntesec-ia/Proyecto-Dashboard/mysite
EnvironmentFile=/home/inntesec-ia/Proyecto-Dashboard/.env
ExecStart=/home/inntesec-ia/Proyecto-Dashboard/venv/bin/celery -A mysite worker -l info --concurrency=4 --pidfile=/var/run/celery/worker.pid
Restart=always

[Install]
WantedBy=multi-user.target
```

Troubleshooting
- If `celery` complains about not finding the Django settings, ensure you're running from the `mysite/` directory so `mysite.settings` is importable, or set `PYTHONPATH` accordingly.
- If beat fails due to a corrupted schedule DB, remove `celerybeat-schedule` and restart.

Contact: repo maintainer
