"""Start the private live email worker and scheduler after connection validation."""
import os
from pathlib import Path
import subprocess
import sys

base = Path(__file__).resolve().parent.parent
result = subprocess.run([sys.executable, str(base / 'scripts/check_live_worker.py')], cwd=base)
if result.returncode:
    raise SystemExit(result.returncode)
env = os.environ.copy()
env['DJANGO_SETTINGS_MODULE'] = 'config.live_worker_settings'
# The local private settings intentionally override a separately configured broker.
env.pop('CELERY_BROKER_URL', None)
flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
for role, extra in [('worker', ['--pool=solo', '--concurrency=1']),
                    ('beat', ['--schedule=tmp/live-celerybeat-schedule'])]:
    pidfile = base / 'tmp' / f'live-celery-{role}.pid'
    if pidfile.exists():
        print(f'{role} PID file already exists. Check the existing process before restarting.')
        continue
    command = [sys.executable, '-m', 'celery', '-A', 'config', role, '--loglevel=INFO',
               f'--logfile=tmp/live-celery-{role}.log', f'--pidfile={pidfile}', *extra]
    with (base / 'tmp' / f'live-celery-{role}-startup.log').open('ab') as log:
        subprocess.Popen(command, cwd=base, env=env, creationflags=flags, stdout=log, stderr=log)
    print(f'{role} launch requested. Check tmp/live-celery-{role}.log for readiness.')
