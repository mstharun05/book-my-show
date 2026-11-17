from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from bookings.models import Booking, ShowSeat
from bookings.services import lock_show, retry_contention
from .models import Payment, PaymentAttempt


def release_booking(booking):
    if booking.status == "PENDING":
        booking.showseat_set.filter(status="RESERVED").update(
            status="AVAILABLE", reserved_until=None, booking=None
        )
        booking.status = "CANCELLED"
        booking.save(update_fields=["status"])


@retry_contention
def apply_payment(entity):
    """Apply an authenticated gateway entity; terminal results never regress."""
    payment = Payment.objects.select_related("booking").get(
        razorpay_order_id=entity["order_id"]
    )
    with transaction.atomic():
        lock_show(payment.booking.show_id)
        payment.refresh_from_db()
        booking = Booking.objects.get(pk=payment.booking_id)
        transaction_id = entity["id"]
        status = entity["status"]
        amount = Decimal(str(entity["amount"])) / 100
        if entity.get("currency") != "INR" or amount != payment.amount:
            raise ValueError("Payment amount or currency mismatch.")
        attempt, created = PaymentAttempt.objects.get_or_create(
            transaction_id=transaction_id,
            defaults={"payment": payment, "status": status, "amount": amount},
        )
        if attempt.payment_id != payment.pk:
            raise ValueError("Transaction belongs to another order.")
        if not created and attempt.status in ("captured", "REFUND_REQUIRED", "refunded"):
            return payment
        attempt.status = status
        attempt.error = entity.get("error_description") or ""
        # New attempts were created with this status, so process them as well.
        attempt.save()
        if status == "captured":
            if payment.status == "SUCCESS":
                if payment.razorpay_payment_id != transaction_id:
                    attempt.status = "REFUND_REQUIRED"
                    attempt.save(update_fields=["status"])
                return payment
            seats = booking.showseat_set.filter(
                status="RESERVED", reserved_until__gt=timezone.now()
            )
            if booking.status != "PENDING" or not seats.exists() or (
                booking.show.ticket_price * seats.count() != amount
            ):
                release_booking(booking)
                payment.status = "REFUND_REQUIRED"
                attempt.status = "REFUND_REQUIRED"
                attempt.save(update_fields=["status"])
            else:
                seats.update(status="BOOKED", reserved_until=None)
                booking.status = "CONFIRMED"
                booking.save(update_fields=["status"])
                payment.status = "SUCCESS"
            payment.razorpay_payment_id = transaction_id
            payment.save(update_fields=["status", "razorpay_payment_id"])
            if payment.status == "SUCCESS":
                # Outbox commits with payment; no broker or SMTP call in checkout.
                from tickets.models import TicketDelivery
                TicketDelivery.objects.get_or_create(booking=booking)
        elif status == "failed" and payment.status not in ("SUCCESS", "REFUND_REQUIRED", "REFUNDED"):
            payment.status = "FAILED"
            payment.save(update_fields=["status"])
            release_booking(booking)
        return payment


@retry_contention
def cancel_booking(booking_id):
    booking = Booking.objects.get(pk=booking_id)
    with transaction.atomic():
        lock_show(booking.show_id)
        booking.refresh_from_db()
        release_booking(booking)
        if booking.status == "CANCELLED":
            booking.payments.filter(status="CREATED").update(status="CANCELLED")
        return booking
