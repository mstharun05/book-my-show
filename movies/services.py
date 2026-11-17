from datetime import timedelta

from django.db.models import F
from django.utils import timezone

from bookings.models import Booking


def completed_bookings(bookings):
    now = timezone.now()
    candidates = bookings.filter(
        status="CONFIRMED",
        show__show_time__lte=now,
        showseat__show_id=F("show_id"),
        showseat__status="BOOKED",
    ).select_related("show__movie").distinct()
    return [
        booking.pk for booking in candidates
        if booking.show.show_time + timedelta(minutes=booking.show.movie.duration) <= now
    ]


def can_review_movie(user, movie):
    return user.is_authenticated and bool(completed_bookings(Booking.objects.filter(
        user=user, show__movie=movie, attended_at__isnull=False,
    )))
