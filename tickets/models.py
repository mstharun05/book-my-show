from django.db import models

from django.utils import timezone


class TicketDelivery(models.Model):
    booking = models.OneToOneField('bookings.Booking', on_delete=models.CASCADE, related_name='ticket_delivery')
    pdf = models.BinaryField(default=bytes, blank=True)
    attempts = models.PositiveIntegerField(default=0)
    next_attempt_at = models.DateTimeField(default=timezone.now)
    sent_at = models.DateTimeField(null=True, blank=True)
    last_error = models.CharField(max_length=120, blank=True)

    class Meta:
        indexes = [models.Index(fields=['sent_at', 'next_attempt_at'])]
