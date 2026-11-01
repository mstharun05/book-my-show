from io import BytesIO

import qrcode
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404

from bookings.models import Booking


@login_required
def download_ticket(request, booking_id):
    booking = get_object_or_404(
        Booking.objects.select_related(
            'user', 'show__movie', 'show__screen__theater'
        ),
        id=booking_id
    )

    # Users can download only their own tickets.
    if booking.user != request.user and not request.user.is_staff:
        return HttpResponseForbidden("You cannot access this ticket.")

    if booking.status != 'CONFIRMED':
        return HttpResponse("Ticket is available only for confirmed bookings.")

    movie = booking.show.movie
    show = booking.show

    seats = booking.show.showseat_set.select_related('seat').filter(
        booking=booking
    )
    seat_numbers = ", ".join(item.seat.seat_number for item in seats) or "Not assigned"

    # Create QR code containing the booking reference.
    qr_image = qrcode.make(f"BOOKING-{booking.id}")
    qr_buffer = BytesIO()
    qr_image.save(qr_buffer, format="PNG")
    qr_buffer.seek(0)

    # Create PDF.
    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = (
        f'attachment; filename="movie_ticket_{booking.id}.pdf"'
    )

    pdf = canvas.Canvas(response, pagesize=A4)
    pdf.setTitle(f"Movie Ticket {booking.id}")

    pdf.setFont("Helvetica-Bold", 22)
    pdf.drawString(60, 780, "BOOK MY SHOW - MOVIE TICKET")

    pdf.setFont("Helvetica", 12)
    pdf.drawString(60, 730, f"Booking ID: {booking.id}")
    pdf.drawString(60, 700, f"Movie: {movie.title}")
    pdf.drawString(60, 670, f"Customer: {booking.user.username}")
    pdf.drawString(60, 640, f"Show time: {show.show_time}")
    pdf.drawString(60, 610, f"Theater: {show.screen.theater.name}")
    pdf.drawString(60, 580, f"Screen: {show.screen.name}")
    pdf.drawString(60, 550, f"Seats: {seat_numbers}")
    pdf.drawString(60, 520, f"Booking status: {booking.status}")

    pdf.drawImage(qr_buffer, 60, 330, width=130, height=130)

    pdf.setFont("Helvetica-Oblique", 10)
    pdf.drawString(60, 300, "Show this QR code at the theater.")
    pdf.drawString(60, 280, "Thank you for booking with us!")

    pdf.save()
    return response