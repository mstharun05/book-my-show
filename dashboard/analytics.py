from datetime import datetime, time, timedelta

from django import forms
from django.contrib.auth import get_user_model
from django.db.models import Count, Sum, Q, OuterRef, Subquery, IntegerField
from django.db.models.functions import TruncDate, TruncMonth, ExtractHour, Coalesce
from django.utils import timezone

from bookings.models import Booking, Show, ShowSeat, Seat, Theater
from payments.models import Payment, PaymentAttempt


class DateRangeForm(forms.Form):
    start = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
    end = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))

    def clean(self):
        data = super().clean()
        today = timezone.localdate()
        data["start"] = data.get("start") or today.replace(day=1)
        data["end"] = data.get("end") or today
        if data["start"] > data["end"]:
            raise forms.ValidationError("Start date must be on or before end date.")
        return data


def midnight(day):
    return timezone.make_aware(datetime.combine(day, time.min))


def analytics(start, end):
    lower, upper = midnight(start), midnight(end + timedelta(days=1))
    bookings = Booking.objects.filter(created_at__gte=lower, created_at__lt=upper)
    payments = Payment.objects.filter(created_at__gte=lower, created_at__lt=upper)
    users = get_user_model().objects.filter(date_joined__gte=lower, date_joined__lt=upper)
    today = timezone.localdate()
    tomorrow = midnight(today + timedelta(days=1))
    periods = {
        "daily": today,
        "weekly": today - timedelta(days=today.weekday()),
        "monthly": today.replace(day=1),
        "yearly": today.replace(month=1, day=1),
    }
    totals = payments.aggregate(
        revenue=Sum("amount", filter=Q(status="SUCCESS"), default=0),
        refunded=Sum("amount", filter=Q(status="REFUNDED"), default=0),
        refund_count=Count("id", filter=Q(status="REFUNDED")),
        failed=Count("id", filter=Q(status="FAILED")),
    )
    # Calendar-to-date cards use one query, independent of the selected range.
    calendar_revenue = Payment.objects.filter(
        status="SUCCESS", created_at__gte=midnight(min(periods.values())), created_at__lt=tomorrow
    ).aggregate(**{
        key: Sum("amount", filter=Q(created_at__gte=midnight(day)), default=0)
        for key, day in periods.items()
    })
    booking_totals = bookings.aggregate(
        total=Count("id"), confirmed=Count("id", filter=Q(status="CONFIRMED")),
        cancelled=Count("id", filter=Q(status="CANCELLED")),
        pending=Count("id", filter=Q(status="PENDING")),
    )
    booking_totals["cancellation_percent"] = round(
        100 * booking_totals["cancelled"] / (booking_totals["total"] or 1), 1
    )
    bucket = TruncDate if (end-start).days <= 90 else TruncMonth
    trends = list(bookings.annotate(period=bucket("created_at")).values("period").annotate(
        total=Count("id"), confirmed=Count("id", filter=Q(status="CONFIRMED")),
        cancelled=Count("id", filter=Q(status="CANCELLED")),
    ).order_by("period"))
    growth = list(users.annotate(period=bucket("date_joined")).values("period").annotate(
        total=Count("id")
    ).order_by("period"))
    movies = list(bookings.filter(status="CONFIRMED").values(
        "show__movie_id", "show__movie__title"
    ).annotate(total=Count("id")).order_by("-total", "show__movie_id")[:10])
    top_theaters = list(payments.filter(status="SUCCESS").values(
        "booking__show__screen__theater_id", "booking__show__screen__theater__name"
    ).annotate(revenue=Sum("amount"), transactions=Count("id")).order_by(
        "-revenue", "booking__show__screen__theater_id"
    )[:10])
    hours = list(bookings.annotate(hour=ExtractHour("created_at")).values("hour").annotate(
        total=Count("id")
    ).order_by("hour"))
    capacity = Seat.objects.filter(screen_id=OuterRef("screen_id")).order_by().values(
        "screen_id"
    ).annotate(n=Count("id")).values("n")
    occupancy = list(Show.objects.filter(show_time__gte=lower, show_time__lt=upper).values(
        "screen__theater_id", "screen__theater__name"
    ).annotate(
        capacity=Sum(Coalesce(Subquery(capacity, output_field=IntegerField()), 0)),
        shows=Count("id"),
    ).order_by("screen__theater__name", "screen__theater_id"))
    occupied = dict(ShowSeat.objects.filter(
        show__show_time__gte=lower, show__show_time__lt=upper,
        status="BOOKED", booking__status="CONFIRMED",
    ).values("show__screen__theater_id").annotate(n=Count("id")).values_list(
        "show__screen__theater_id", "n"
    ))
    scheduled = {row["screen__theater_id"] for row in occupancy}
    occupancy.extend(
        {"screen__theater_id": pk, "screen__theater__name": name, "capacity": 0, "shows": 0}
        for pk, name in Theater.objects.exclude(pk__in=scheduled).order_by("name", "pk").values_list("pk", "name")
    )
    for row in occupancy:
        row["booked"] = occupied.get(row["screen__theater_id"], 0)
        row["percentage"] = round(100 * row["booked"] / (row["capacity"] or 1), 1)
    refunds_pending = PaymentAttempt.objects.filter(
        created_at__gte=lower, created_at__lt=upper, status="REFUND_REQUIRED"
    ).aggregate(count=Count("id"), amount=Sum("amount", default=0))
    return {
        "totals": totals, "calendar_revenue": calendar_revenue, "booking_totals": booking_totals,
        "trends": trends, "growth": growth, "new_users": users.count(),
        "movies": movies, "theaters": top_theaters, "hours": hours,
        "occupancy": occupancy, "refunds_pending": refunds_pending,
        "bucket": "daily" if bucket == TruncDate else "monthly",
    }
