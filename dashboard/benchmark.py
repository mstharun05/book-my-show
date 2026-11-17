"""Run with the project interpreter. Uses an isolated temporary SQLite database."""
import os
import sys
import tempfile
from datetime import timedelta
from pathlib import Path
from statistics import median
from time import perf_counter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
from django.conf import settings

with tempfile.TemporaryDirectory(prefix="movie-analytics-benchmark-") as directory:
    settings.DATABASES["default"] = {"ENGINE":"django.db.backends.sqlite3", "NAME":str(Path(directory)/"benchmark.sqlite3")}
    import django
    django.setup()
    from django.core.management import call_command
    from django.db import connection
    from django.db.models import Sum
    from django.test.utils import CaptureQueriesContext
    from django.utils import timezone
    from django.contrib.auth.models import User
    from movies.models import Movie
    from bookings.models import Theater, Screen, Seat, Show, Booking
    from payments.models import Payment
    from dashboard.analytics import analytics, midnight
    from discovery.views import filtered_movies

    call_command("migrate", verbosity=0)
    user = User.objects.create(username="benchmark")
    movies = [Movie.objects.create(title=f"Benchmark {n}",duration=120,release_date=timezone.localdate()) for n in range(10)]
    theaters = [Theater.objects.create(name=f"Theater {n}",city="Benchmark") for n in range(5)]
    screens = [Screen.objects.create(theater=theater,name="Screen") for theater in theaters]
    Seat.objects.bulk_create([Seat(screen=screen,seat_number=str(n)) for screen in screens for n in range(40)])
    shows = [Show.objects.create(movie=movies[n%10],screen=screens[n%5],show_time=timezone.now()+timedelta(days=n%30),ticket_price=200) for n in range(100)]
    for offset in range(0,100000,2000):
        bookings = Booking.objects.bulk_create([
            Booking(user=user,show=shows[n%100],status="CANCELLED" if n%10==0 else "CONFIRMED")
            for n in range(offset,offset+2000)
        ])
        Payment.objects.bulk_create([
            Payment(booking=booking,amount=200,status="FAILED" if booking.status=="CANCELLED" else "SUCCESS")
            for booking in bookings
        ])
    # Spread fixture dates over one year with equal distributions on both tables.
    with connection.cursor() as cursor:
        for table in ("bookings_booking", "payments_payment"):
            cursor.execute(f"UPDATE {table} SET created_at = datetime('now', '-' || (id % 365) || ' days')")
        cursor.execute("ANALYZE")
    today = timezone.localdate()
    start=today-timedelta(days=29)
    def timed(function):
        values=[]
        for _ in range(3):
            begin=perf_counter()
            function()
            values.append((perf_counter()-begin)*1000)
        return round(median(values),2)
    baseline = lambda: Payment.objects.filter(status="SUCCESS",created_at__date=today).aggregate(value=Sum("amount"))
    optimized = lambda: Payment.objects.filter(status="SUCCESS",created_at__gte=midnight(today),created_at__lt=midnight(today+timedelta(days=1))).aggregate(value=Sum("amount"))
    old_ms, new_ms = timed(baseline), timed(optimized)
    full_ms = timed(lambda: analytics(start,today))
    with CaptureQueriesContext(connection) as captured:
        analytics(start,today)
    discovery_ms = timed(lambda:list(filtered_movies({"sort":"popular"})[:8]))
    plan = Payment.objects.filter(status="SUCCESS",created_at__gte=midnight(today),created_at__lt=midnight(today+timedelta(days=1))).explain()
    report = Path(__file__).resolve().parents[1]/"ADMIN_DASHBOARD_REPORT.md"
    with report.open("a",encoding="utf-8") as handle:
        handle.write(f"""
## Measured performance

Measured locally with an isolated SQLite database containing 100,000 bookings, 100,000 payment orders, 100 shows, 10 movies and 5 theaters. Dates were distributed over 365 days. Medians use three warm runs. The application database was not populated by this benchmark.

| Measurement | Time |
|---|---|
| Previous date-extraction daily revenue filter | {old_ms} ms |
| Indexed timestamp-range daily revenue filter | {new_ms} ms |
| Complete selected 30-day dashboard aggregation | {full_ms} ms |
| Popularity-sorted discovery page, 8 movies | {discovery_ms} ms |

The timestamp filter improved the measured daily revenue query by {round(old_ms/max(new_ms,0.01),1)} times. Full dashboard aggregation executed {len(captured)} SQL queries. Results are local measurements, not a production latency guarantee. Different database engines, hardware, data distributions, concurrent load and catalog sizes require their own load tests.

The optimized daily revenue query plan was

```text
{plan}
```

Reproduce with `venv/Scripts/python.exe dashboard/benchmark.py`. It creates and removes a temporary database automatically.
""")
    print(f"100,000-booking benchmark complete. Dashboard {full_ms} ms, {len(captured)} queries. Daily filter {old_ms} -> {new_ms} ms. Discovery {discovery_ms} ms.")
    connection.close()
