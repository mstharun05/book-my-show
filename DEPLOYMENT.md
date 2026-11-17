# Deploy this version on the existing Render service

Use the existing service linked to `mstharun05/book-my-show`, branch `main`. Set Build Command to `bash build.sh`, Start Command to `bash start.sh`, and Health Check Path to `/health/`. Deploy the latest commit after pushing. The start script applies migrations and imports the existing public catalog only into an empty movie catalog.

Required private environment variables: `DATABASE_URL` (PostgreSQL), `SECRET_KEY`, `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`, and `RAZORPAY_WEBHOOK_SECRET`. Keep `DEBUG=False`. Render's public hostname automatically configures allowed hosts, CSRF and ticket verification links. Optional first-deploy admin variables: `DJANGO_SUPERUSER_USERNAME`, `DJANGO_SUPERUSER_PASSWORD`, `DJANGO_SUPERUSER_EMAIL`. Existing admins are not overwritten.

`render.yaml` is an alternative for a NEW free web service/database. Do not apply it blindly to an existing service: that can create a second database. The existing service needs the commands above configured in its Dashboard.

Verify `/health/`, `/movies/`, `/accounts/login/`, `/accounts/signup/`, and all five `/explore/` categories after Render reports Live. Verify that private booking history redirects signed-out visitors to login. Complete a Razorpay test payment before claiming payment readiness, and register the HTTPS `/payments/webhook/` URL in Razorpay with the matching private webhook secret.

## Submission limitations

- The free Render web service sleeps when idle; the free PostgreSQL database expires after 30 days. Keep a database backup before expiry.
- Free Render hosting does not include a Celery worker and blocks Gmail SMTP. Ticket PDF downloads work independently; automatic email requires a separate worker and configured mail provider. Do not claim email delivery has been verified until it has been tested.
- Stream shows official trailers, not licensed full movies.
- Events, Plays, Sports and Activities are searchable admin-managed listings. They initially have no published listings. Their booking links go to an organizer's website when an admin supplies a valid URL; they do not use the movie seat checkout.
- The catalog fixture contains public movie, venue, seat and show data only; it excludes users, reviews, bookings, payment records and secrets. Existing show dates are retained. Admins must add current showtimes as needed.

Store submission admin credentials in the private submission report, never in GitHub.
