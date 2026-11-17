
from django.db import models
from bookings.models import Booking


class Payment(models.Model):

    STATUS_CHOICES = [
        ('CREATED', 'Created'),
        ('SUCCESS', 'Success'),
        ('FAILED', 'Failed'),
        ('REFUNDED', 'Refunded'),
        ('CANCELLED', 'Cancelled'),
        ('REFUND_REQUIRED', 'Refund required'),
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
        null=True, blank=True,
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

    class Meta:
        indexes = [
            models.Index(fields=["created_at", "status"], name="payment_date_status_idx"),
            models.Index(fields=["status", "created_at"], name="payment_status_date_idx"),
        ]

    def __str__(self):
        return f"Payment #{self.id} - {self.status}"


class PaymentAttempt(models.Model):
    payment = models.ForeignKey(Payment, on_delete=models.CASCADE, related_name="attempts")
    transaction_id = models.CharField(max_length=200, unique=True)
    status = models.CharField(max_length=30)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


    class Meta:
        indexes = [models.Index(fields=["status", "created_at"], name="attempt_status_date_idx")]
