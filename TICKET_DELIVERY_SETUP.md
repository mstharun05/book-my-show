# Ticket generation and delivery

Payment verification now writes one TicketDelivery outbox row in the same database transaction as confirmation. Checkout makes no SMTP or broker calls. Celery beat polls the indexed outbox every 15 seconds and publishes delivery jobs. PDF bytes are stored privately in the database, and downloads check ownership and current paid booking status. Existing confirmed, paid bookings can generate their ticket through booking history.

Tickets include the movie, certificate, duration, theater, screen, local show time, seat numbers, booking ID, amount and payment reference. The signed QR URL requires a logged-in account with `bookings.view_booking` permission and rechecks payment/booking status. It verifies authenticity; it is not a single-use admission/check-in system.

## Configure services

### This Windows computer

The ignored `delivery.local.json` supplies Gmail sender settings and `local-sqlite` for a local disk-backed Celery queue. Environment variables override it. The queue is under `tmp/celery-queue.sqlite3`; use this on one computer only, and retain Redis for production. Enter the Google app password through `venv/Scripts/pythonw.exe scripts/configure_ticket_email.py`; it is saved only in the ignored local configuration. Restart the web server and worker after credential changes. Do not commit or share that file.

Local background processes use the solo worker pool. Their logs and PID files are `tmp/celery-worker.log`, `tmp/celery-worker.pid`, `tmp/celery-beat.log` and `tmp/celery-beat.pid`. They must be restarted after a computer restart; these are development processes, not installed Windows services. The queue uses [Kombu's SQLAlchemy transport](https://docs.celeryq.dev/projects/kombu/en/stable/reference/kombu.transport.sqlalchemy.html).

### Production services

Install requirements and run `python manage.py migrate`. Set these environment variables in the web, worker and beat services (a `.env` file is not automatically loaded):

```
CELERY_BROKER_URL=redis://HOST:6379/0
SITE_URL=https://your-application.example
SECRET_KEY=your-stable-private-production-key
EMAIL_HOST=your-smtp-host
EMAIL_PORT=587
EMAIL_HOST_USER=your-smtp-user
EMAIL_HOST_PASSWORD=your-smtp-password
EMAIL_USE_TLS=True
EMAIL_USE_SSL=False
DEFAULT_FROM_EMAIL=your-verified-sender@example.com
```

Use `rediss://` if your broker requires TLS. All processes must share the same database and SECRET_KEY. SITE_URL must point to a reachable application for QR scans. Use a verified SMTP sender; do not commit credentials. New signup requires email; existing users can update it from booking history.

Start a worker and exactly one beat scheduler in separate services:

```
python -m celery -A config worker --loglevel=INFO
python -m celery -A config beat --loglevel=INFO
```

For local Windows testing use `worker --pool=solo --loglevel=INFO`. Deploy production workers on Linux. Keep beat's schedule file in a writable persistent working directory. Redis and SMTP must be reachable from the worker. No email services were configured or external emails sent during implementation.

## Reliability and operation

### Free deployment with this computer as the worker

Run `venv/Scripts/pythonw.exe scripts/configure_live_worker.py` to save masked Gmail and production PostgreSQL settings into ignored `tmp/live-worker.json`. The database must be the same PostgreSQL database used by the live web service, with external connectivity allowed for this computer. The SECRET_KEY must match Render. Do not copy an internal-only Render database URL.

Run `venv/Scripts/python.exe scripts/check_live_worker.py` to validate database connectivity and Gmail authentication without sending mail. Then run `venv/Scripts/python.exe scripts/start_live_worker.py` to start a separate solo worker and scheduler. They use the production database for the durable delivery outbox and a separate local SQLite Celery broker. They do not migrate or seed the production database. Keep this computer awake and online, and restart these processes after reboot. Inspect `tmp/live-celery-worker.log` and `tmp/live-celery-beat.log` for readiness/errors. A successfully launched process is not proof of email delivery; confirm the delivery's `sent_at` and recipient inbox.

Delivery claims use an atomic database update and a ten-minute lease. Concurrent jobs and already-sent jobs skip processing. Failed attempts retain the PDF and use durable exponential backoff, starting at 30 seconds and capped at one hour. Beat retries indefinitely, including after broker outages. A crashed worker's lease expires automatically. Delivery state, attempt count and error class are visible in Django Admin under Ticket deliveries. Fix missing addresses through the user's profile; pending deliveries will retry.

SMTP delivery is at-least-once: a worker crash after SMTP acceptance but before recording success can resend a message. A stable Message-ID is included, but SMTP cannot guarantee exactly-once delivery. SMTP acceptance also does not guarantee inbox placement. Payment and booking idempotency remain independent of email delivery.

## Verification

`python manage.py test` passes 32 tests, including six ticket tests covering transactional rollback, duplicate confirmations without network I/O, PDF email attachment and repeat-job suppression, failed delivery/backoff/recovery, owner-only downloads, signed QR permissions/tampering/refunds, and missing-email recovery. PDF layout was separately rendered for visual inspection. Real SMTP/Redis delivery requires the configured services above.

Celery scheduling reference: https://docs.celeryq.dev/en/stable/userguide/periodic-tasks.html
