from django.contrib.auth.decorators import login_required, permission_required
from django.core import signing
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from bookings.models import Booking
from .models import TicketDelivery
from .pdf import render_ticket


@login_required
def download_ticket(request, booking_id):
    bookings = Booking.objects.select_related('user', 'show__movie', 'show__screen__theater')
    if not request.user.has_perm('bookings.view_booking'):
        bookings = bookings.filter(user=request.user)
    booking = get_object_or_404(bookings, pk=booking_id, status='CONFIRMED', payments__status='SUCCESS')
    delivery, _ = TicketDelivery.objects.get_or_create(booking=booking)
    if not delivery.pdf:
        delivery.pdf = render_ticket(booking)
        delivery.save(update_fields=['pdf'])
    response = HttpResponse(bytes(delivery.pdf), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="movie_ticket_{booking.pk}.pdf"'
    response['Cache-Control'] = 'private, no-store'
    return response


@login_required
@permission_required('bookings.view_booking', raise_exception=True)
def verify_ticket(request, token):
    try:
        booking_id = signing.Signer(salt='movie-ticket-v1').unsign(token)
        booking = get_object_or_404(Booking.objects.select_related('show__movie', 'show__screen__theater'), pk=int(booking_id), status='CONFIRMED', payments__status='SUCCESS')
    except (signing.BadSignature, ValueError):
        return JsonResponse({'valid': False}, status=400)
    return JsonResponse({'valid': True, 'booking_id': booking.pk, 'movie': booking.show.movie.title,
        'theater': booking.show.screen.theater.name, 'screen': booking.show.screen.name,
        'show_time': booking.show.show_time.isoformat(), 'seats': booking.seat_numbers})
