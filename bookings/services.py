
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from .models import Show, Seat, Booking, ShowSeat


class SeatUnavailableError(Exception):
    pass


@transaction.atomic
def release_expired_seats(show_id=None):
    """
    Release reservations whose two-minute expiry has passed.
    """

    now = timezone.now()

    expired = ShowSeat.objects.filter(
        status="RESERVED",
        reserved_until__lte=now
    )

    if show_id is not None:
        expired = expired.filter(show_id=show_id)

    booking_ids = list(
        expired.exclude(booking=None)
        .values_list("booking_id", flat=True)
        .distinct()
    )

    expired.update(
        status="AVAILABLE",
        reserved_until=None,
        booking=None
    )

    # Cancel pending bookings that no longer have reserved seats.
    for booking_id in booking_ids:
        still_reserved = ShowSeat.objects.filter(
            booking_id=booking_id,
            status="RESERVED",
            reserved_until__gt=now
        ).exists()

        if not still_reserved:
            Booking.objects.filter(
                id=booking_id,
                status="PENDING"
            ).update(status="CANCELLED")


@transaction.atomic
def reserve_seats(user, show_id, seat_ids):

    if not isinstance(seat_ids, (list, tuple)):
        raise ValueError("Seat IDs must be a list.")

    if not seat_ids:
        raise ValueError("Please select at least one seat.")

    try:
        seat_ids = list(set(int(seat_id) for seat_id in seat_ids))
    except (ValueError, TypeError):
        raise ValueError("Invalid seat selection.")

    if any(seat_id <= 0 for seat_id in seat_ids):
        raise ValueError("Invalid seat selection.")

    # Lock the show to serialize competing reservations.
    show = Show.objects.select_for_update().select_related(
        "screen"
    ).get(id=show_id)

    # Release expired reservations before checking availability.
    release_expired_seats(show_id=show.id)

    valid_seats = Seat.objects.filter(
        screen=show.screen,
        id__in=seat_ids
    )

    if valid_seats.count() != len(seat_ids):
        raise ValueError("Invalid seat selection.")

    # Create missing availability records.
    existing_ids = set(
        ShowSeat.objects.filter(
            show=show
        ).values_list("seat_id", flat=True)
    )

    missing_seats = [
        ShowSeat(show=show, seat=seat)
        for seat in valid_seats
        if seat.id not in existing_ids
    ]

    ShowSeat.objects.bulk_create(
        missing_seats,
        ignore_conflicts=True
    )

    # Lock selected seat records.
    selected_seats = list(
        ShowSeat.objects.select_for_update()
        .filter(show=show, seat_id__in=seat_ids)
        .select_related("seat")
        .order_by("id")
    )

    now = timezone.now()

    for show_seat in selected_seats:

        if show_seat.status == "BOOKED":
            raise SeatUnavailableError(
                f"Seat {show_seat.seat.seat_number} is already booked."
            )

        if show_seat.status == "RESERVED":
            if (
                show_seat.reserved_until is None
                or show_seat.reserved_until > now
            ):
                raise SeatUnavailableError(
                    f"Seat {show_seat.seat.seat_number} is already reserved."
                )

    # Create pending booking.
    booking = Booking.objects.create(
        user=user,
        show=show,
        status="PENDING"
    )

    # Reserve seats for two minutes.
    expiry_time = now + timedelta(minutes=2)

    for show_seat in selected_seats:
        show_seat.status = "RESERVED"
        show_seat.reserved_until = expiry_time
        show_seat.booking = booking

    ShowSeat.objects.bulk_update(
        selected_seats,
        ["status", "reserved_until", "booking"]
    )

    return booking
