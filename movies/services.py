
from django.utils import timezone
from bookings.models import Booking, ShowSeat


def can_review_movie(user, movie):
    if not user.is_authenticated:
        return False

    return Booking.objects.filter(
        user=user,
        show__movie=movie,
        show__show_time__lt=timezone.now(),
        status="CONFIRMED",
        showseat__status="BOOKED"
    ).exists()
