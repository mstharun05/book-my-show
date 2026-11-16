import json

from .services import reserve_seats, release_expired_seats, SeatUnavailableError
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render
from django.http import JsonResponse
from django.utils import timezone

from .models import Show, ShowSeat, Seat
from .services import release_expired_seats


def seat_availability(request, show_id):
    show = get_object_or_404(Show, id=show_id)

    # Release expired reservations after retrieving the show
    release_expired_seats(show_id=show.id)

    seats = Seat.objects.filter(
        screen=show.screen
    ).order_by("seat_number")

    show_seats = {
        item.seat_id: item
        for item in ShowSeat.objects.filter(show=show)
    }

    now = timezone.now()
    seat_data = []

    for seat in seats:
        show_seat = show_seats.get(seat.id)
        status = "AVAILABLE"

        if show_seat:
            if show_seat.status == "BOOKED":
                status = "BOOKED"
            elif show_seat.status == "RESERVED":
                if show_seat.reserved_until and show_seat.reserved_until > now:
                    status = "RESERVED"

        seat_data.append({
            "id": seat.id,
            "seat_number": seat.seat_number,
            "status": status
        })

    return JsonResponse({
        "show_id": show.id,
        "movie": show.movie.title,
        "ticket_price": str(show.ticket_price),
        "seats": seat_data
    })
 
@login_required
def seat_selection_page(request, show_id):
    show = get_object_or_404(
        Show.objects.select_related("movie", "screen"),
        id=show_id
    )

    return render(
        request,
        "bookings/seat_selection.html",
        {"show": show}
    )

@login_required
@require_POST
def reserve_selected_seats(request, show_id):
    try:
        data = json.loads(request.body)
        seat_ids = data.get("seat_ids", [])

        if not isinstance(seat_ids, list):
            return JsonResponse(
                {"error": "Seat IDs must be a list."},
                status=400
            )

        booking = reserve_seats(
            user=request.user,
            show_id=show_id,
            seat_ids=seat_ids
        )

        return JsonResponse({
            "message": "Seats reserved successfully.",
            "booking_id": booking.id,
            "expires_in_seconds": 120
        }, status=201)

    except SeatUnavailableError as error:
        return JsonResponse({"error": str(error)}, status=409)

    except (ValueError, TypeError, json.JSONDecodeError) as error:
        return JsonResponse({"error": str(error)}, status=400)
