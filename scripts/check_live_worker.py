"""Read-only connection checks; only safe status and exception class are printed."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.live_worker_settings'
try:
    import django
    django.setup()
    from django.core.mail import get_connection
    from tickets.models import TicketDelivery
    pending = TicketDelivery.objects.filter(sent_at__isnull=True).count()
    print(f'Production ticket queue reachable. Pending deliveries: {pending}', flush=True)
    connection = get_connection()
    connection.open()
    connection.close()
    print('Gmail authenticated successfully. No test email sent.', flush=True)
except Exception as exc:
    print('Connection check failed: ' + type(exc).__name__, flush=True)
    sys.exit(1)
