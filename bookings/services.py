from datetime import timedelta
from functools import wraps
from time import sleep

from django.db import OperationalError, transaction
from django.db.models import F
from django.utils import timezone

from .models import Show, Seat, Booking, ShowSeat


class SeatUnavailableError(Exception):
    pass



def retry_contention(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        for attempt in range(6):
            try:
                return function(*args, **kwargs)
            except OperationalError as error:
                if "locked" not in str(error).lower() or attempt == 5:
                    raise
                sleep(0.05 * (attempt + 1))
    return wrapped


def lock_show(show_id):
    # A write lock also serializes SQLite, where select_for_update is a no-op.
    if not Show.objects.filter(pk=show_id).update(ticket_price=F("ticket_price")):
        raise Show.DoesNotExist
    return Show.objects.get(pk=show_id)


@transaction.atomic
def release_expired_seats(show_id=None):
    if show_id is None:
        for pk in Show.objects.order_by("pk").values_list("pk", flat=True):
            release_expired_seats(pk)
        return
    lock_show(show_id)
    expired = ShowSeat.objects.filter(
        show_id=show_id, status="RESERVED", reserved_until__lte=timezone.now()
    )
    booking_ids = list(expired.values_list("booking_id", flat=True))
    expired.update(status="AVAILABLE", reserved_until=None, booking=None)
    Booking.objects.filter(pk__in=booking_ids, status="PENDING").exclude(
        showseat__status="RESERVED"
    ).update(status="CANCELLED")


@retry_contention
@transaction.atomic
def reserve_seats(user, show_id, seat_ids, booking_id=None):
    if not isinstance(seat_ids, (list, tuple)) or any(
        isinstance(pk, bool) or not isinstance(pk, int) or pk <= 0 for pk in seat_ids
    ):
        raise ValueError("Invalid seat selection.")
    seat_ids = sorted(set(seat_ids))
    if not seat_ids and booking_id is None:
        raise ValueError("Please select at least one seat.")

    show = lock_show(show_id)
    if show.show_time <= timezone.now():
        raise ValueError("This show has already started.")
    release_expired_seats(show_id)
    now = timezone.now()
    expiry = now + timedelta(minutes=2)
    previous = None
    if booking_id is not None:
        previous = Booking.objects.filter(
            pk=booking_id, user=user, show=show, status="PENDING"
        ).first()
        if previous is None:
            raise SeatUnavailableError("Reservation expired or unavailable. Select seats again.")
        expiry = ShowSeat.objects.filter(
            booking=previous, status="RESERVED"
        ).values_list("reserved_until", flat=True).first()
        if expiry is None or expiry <= now:
            raise SeatUnavailableError("Reservation expired. Select seats again.")

    valid_seats = list(Seat.objects.filter(screen=show.screen, pk__in=seat_ids))
    if len(valid_seats) != len(seat_ids):
        raise ValueError("Invalid seat selection.")
    ShowSeat.objects.bulk_create(
        [ShowSeat(show=show, seat=seat) for seat in valid_seats],
        ignore_conflicts=True,
    )
    selected = ShowSeat.objects.filter(show=show, seat_id__in=seat_ids)
    unavailable = selected.exclude(status="AVAILABLE")
    if previous:
        unavailable = unavailable.exclude(booking=previous, status="RESERVED")
    if unavailable.exists():
        raise SeatUnavailableError("Some seats are no longer available. Refresh your selection.")
    if previous:
        current_ids = set(previous.showseat_set.values_list("seat_id", flat=True))
        if current_ids == set(seat_ids):
            return previous
        previous.showseat_set.update(status="AVAILABLE", reserved_until=None, booking=None)
        previous.status = "CANCELLED"
        previous.save(update_fields=["status"])
    if not seat_ids:
        return None
    booking = Booking.objects.create(user=user, show=show, seat_numbers=[seat.seat_number for seat in valid_seats])
    selected.update(status="RESERVED", reserved_until=expiry, booking=booking)
    return booking
