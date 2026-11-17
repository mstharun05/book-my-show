import json

from .services import reserve_seats, release_expired_seats, SeatUnavailableError
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render
from django.http import JsonResponse
from django.utils import timezone

from .models import Show, ShowSeat, Seat


def seat_availability(request, show_id):
    show = get_object_or_404(Show, id=show_id)

    # Release expired reservations after retrieving the show
    release_expired_seats(show_id=show.id)

    seats = Seat.objects.filter(
        screen=show.screen
    ).order_by("seat_number")

    show_seats = {
        item.seat_id: item
        for item in ShowSeat.objects.filter(show=show).select_related("booking")
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
            "status": status,
            "owned": bool(show_seat and show_seat.booking_id and
                          request.user.is_authenticated and
                          show_seat.booking.user_id == request.user.id and status == "RESERVED"),
            "booking_id": show_seat.booking_id if show_seat and request.user.is_authenticated and show_seat.booking_id and show_seat.booking.user_id == request.user.id and status == "RESERVED" else None,
            "reserved_until": show_seat.reserved_until if show_seat and status == "RESERVED" else None
        })

    return JsonResponse({
        "server_time": now,
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
        if not isinstance(data, dict):
            raise ValueError("Expected a JSON object.")
        seat_ids = data.get("seat_ids", [])

        if not isinstance(seat_ids, list):
            return JsonResponse(
                {"error": "Seat IDs must be a list."},
                status=400
            )

        booking = reserve_seats(
            user=request.user,
            show_id=show_id,
            seat_ids=seat_ids,
            booking_id=data.get("booking_id")
        )

        return JsonResponse({
            "message": "Seats reserved successfully.",
            "booking_id": booking.id if booking else None,
            "server_time": timezone.now(),
            "reserved_until": booking.showseat_set.first().reserved_until if booking else None
        }, status=201)

    except Show.DoesNotExist:
        return JsonResponse({"error": "Show not found."}, status=404)

    except SeatUnavailableError as error:
        return JsonResponse({"error": str(error)}, status=409)

    except (ValueError, TypeError, json.JSONDecodeError) as error:
        return JsonResponse({"error": str(error)}, status=400)
