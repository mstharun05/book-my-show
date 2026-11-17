from io import BytesIO
from xml.sax.saxutils import escape
import qrcode
from django.conf import settings
from django.core import signing
from django.utils import timezone
from django.urls import reverse
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image


def verification_token(booking):
    return signing.Signer(salt='movie-ticket-v1').sign(str(booking.pk))


def render_ticket(booking):
    payment = booking.payments.filter(status='SUCCESS').first()
    if booking.status != 'CONFIRMED' or not payment:
        raise ValueError('A verified payment is required for a ticket.')
    show = booking.show
    seats = booking.seat_numbers or list(booking.showseat_set.filter(status='BOOKED').values_list('seat__seat_number', flat=True))
    output = BytesIO()
    styles = getSampleStyleSheet()
    styles['Title'].textColor = colors.HexColor('#17243b')
    styles['Title'].alignment = 0
    styles['BodyText'].leading = 16
    def para(value, style='BodyText'):
        return Paragraph(escape(str(value)), styles[style])
    url = settings.SITE_URL + reverse('verify_ticket', args=[verification_token(booking)])
    qr = BytesIO()
    qrcode.make(url).save(qr, format='PNG')
    qr.seek(0)
    story = [para('BOOK MY SHOW / E-TICKET', 'Heading2'), Spacer(1, 20),
             para(show.movie.title, 'Title'), para('PAYMENT VERIFIED  |  Booking #' + str(booking.pk)), Spacer(1, 24)]
    rows = [
        ('THEATER', f'{show.screen.theater.name}, {show.screen.theater.city}'),
        ('SCREEN', show.screen.name),
        ('SHOW TIME', timezone.localtime(show.show_time).strftime('%d %b %Y, %I:%M %p %Z')),
        ('MOVIE DETAILS', f'{show.movie.duration} minutes | Certificate: {show.movie.age_certificate}'),
        ('SEATS', ', '.join(seats)), ('BOOKING ID', booking.pk),
        ('PAYMENT REFERENCE', payment.razorpay_payment_id or payment.razorpay_order_id),
        ('AMOUNT PAID', f'INR {payment.amount:.2f}'),
    ]
    table = Table([[para(label), para(value)] for label, value in rows], colWidths=[140, 335])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#f2f5fa')),
        ('VALIGN', (0,0), (-1,-1), 'TOP'), ('LEFTPADDING', (0,0),(-1,-1),14),
        ('RIGHTPADDING', (0,0),(-1,-1),14), ('TOPPADDING',(0,0),(-1,-1),10),
        ('BOTTOMPADDING',(0,0),(-1,-1),10),
    ]))
    story += [table, Spacer(1, 24), Image(qr, 130, 130, hAlign='LEFT'), Spacer(1, 10),
              para('Show this ticket at the entrance. Theater staff can scan the QR code to verify your booking.'),
              Spacer(1, 10), para('Please arrive 20 minutes before the show. Enjoy the movie!')]
    SimpleDocTemplate(output, title=f'Movie ticket {booking.pk}', leftMargin=60, rightMargin=60, topMargin=40, bottomMargin=40).build(story)
    return output.getvalue()
