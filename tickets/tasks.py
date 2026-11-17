from datetime import timedelta
import logging
from celery import shared_task
from django.core.mail import EmailMessage
from django.db.models import F
from django.utils import timezone
from .models import TicketDelivery
from .pdf import render_ticket

logger = logging.getLogger(__name__)


@shared_task
def dispatch_pending():
    # Bounded indexed scan also recovers broker failures and dead workers.
    ids = list(TicketDelivery.objects.filter(sent_at__isnull=True, next_attempt_at__lte=timezone.now()).values_list('pk', flat=True)[:100])
    for delivery_id in ids:
        deliver_ticket.delay(delivery_id)


@shared_task
def deliver_ticket(delivery_id):
    now = timezone.now()
    # Atomic lease prevents simultaneous workers sending the same ticket.
    claimed = TicketDelivery.objects.filter(pk=delivery_id, sent_at__isnull=True, next_attempt_at__lte=now).update(
        next_attempt_at=now + timedelta(minutes=10), attempts=F('attempts') + 1)
    if not claimed:
        return
    delivery = TicketDelivery.objects.select_related('booking__user', 'booking__show__movie', 'booking__show__screen__theater').get(pk=delivery_id)
    try:
        booking = delivery.booking
        if booking.status != 'CONFIRMED' or not booking.payments.filter(status='SUCCESS').exists():
            raise ValueError('Booking is not paid and confirmed')
        if not delivery.pdf:
            delivery.pdf = render_ticket(booking)
            delivery.save(update_fields=['pdf'])
        if not booking.user.email:
            raise ValueError('Account email address is missing')
        email = EmailMessage(
            subject=f'Your movie ticket - Booking #{booking.pk}',
            body=f'Your booking for {booking.show.movie.title} is confirmed. Your PDF ticket is attached. You can also download it from your booking history.',
            to=[booking.user.email], headers={'Message-ID': f'<movie-ticket-{booking.pk}@bookmyshow.local>'})
        email.attach(f'movie_ticket_{booking.pk}.pdf', bytes(delivery.pdf), 'application/pdf')
        if email.send(fail_silently=False) != 1:
            raise RuntimeError('Email backend did not accept message')
    except Exception as exc:
        # Persist backoff so retry does not depend on a broker publish succeeding.
        delay = min(3600, 30 * 2 ** min(delivery.attempts - 1, 7))
        TicketDelivery.objects.filter(pk=delivery_id).update(next_attempt_at=timezone.now()+timedelta(seconds=delay), last_error=type(exc).__name__)
        logger.warning('Ticket delivery %s failed (%s); retry in %ss', delivery_id, type(exc).__name__, delay)
        return
    TicketDelivery.objects.filter(pk=delivery_id).update(sent_at=timezone.now(), last_error='')
