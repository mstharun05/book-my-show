
from django.db import models
from bookings.models import Booking


class Payment(models.Model):

    STATUS_CHOICES = [
        ('CREATED', 'Created'),
        ('SUCCESS', 'Success'),
        ('FAILED', 'Failed'),
        ('REFUNDED', 'Refunded'),
    ]

    booking = models.ForeignKey(
        Booking,
        on_delete=models.CASCADE,
        related_name='payments'
    )

    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    razorpay_order_id = models.CharField(
        max_length=200,
        unique=True
    )

    razorpay_payment_id = models.CharField(
        max_length=200,
        unique=True,
        null=True,
        blank=True
    )

    razorpay_signature = models.CharField(
        max_length=500,
        blank=True
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='CREATED'
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Payment #{self.id} - {self.status}"
