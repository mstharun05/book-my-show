
import json
import logging
from decimal import Decimal

import razorpay

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST
from django.utils import timezone

from bookings.models import Booking, ShowSeat
from .models import Payment


logger = logging.getLogger(__name__)


def razorpay_client():
    key_id = getattr(settings, "RAZORPAY_KEY_ID", "")
    key_secret = getattr(settings, "RAZORPAY_KEY_SECRET", "")

    if not key_id or not key_secret:
        raise ValueError(
            "Razorpay test keys are missing. Configure "
            "RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET."
        )

    return razorpay.Client(auth=(key_id, key_secret))


@login_required
@require_POST
def create_payment_order(request, booking_id):
    booking = get_object_or_404(
        Booking,
        id=booking_id,
        user=request.user
    )

    if booking.status != "PENDING":
        return JsonResponse(
            {"error": "Booking is not pending."},
            status=400
        )

    now = timezone.now()

    reserved_seats = ShowSeat.objects.filter(
        booking=booking,
        status="RESERVED",
        reserved_until__gt=now
    )

    seat_count = reserved_seats.count()

    if seat_count == 0:
        return JsonResponse(
            {"error": "Seat reservation has expired."},
            status=400
        )

    amount = (
        Decimal(str(booking.show.ticket_price))
        * seat_count
    )

    amount_paise = int(amount * 100)

    try:
        client = razorpay_client()

        # Reuse an existing created order for this booking.
        existing_payment = Payment.objects.filter(
            booking=booking,
            status="CREATED"
        ).order_by("-id").first()

        if existing_payment:
            return JsonResponse({
                "key_id": settings.RAZORPAY_KEY_ID,
                "order_id": existing_payment.razorpay_order_id,
                "amount": amount_paise,
                "currency": "INR",
                "booking_id": booking.id
            })

        order = client.order.create({
            "amount": amount_paise,
            "currency": "INR",
            "payment_capture": 1,
            "receipt": f"booking_{booking.id}"
        })

        Payment.objects.create(
            booking=booking,
            amount=amount,
            razorpay_order_id=order["id"],
            status="CREATED"
        )

        return JsonResponse({
            "key_id": settings.RAZORPAY_KEY_ID,
            "order_id": order["id"],
            "amount": amount_paise,
            "currency": "INR",
            "booking_id": booking.id
        })

    except Exception:
        logger.exception("Razorpay order creation failed")
        return JsonResponse(
            {
                "error": (
                    "Unable to create payment order. "
                    "Check Razorpay test keys and server logs."
                )
            },
            status=500
        )


@login_required
@require_POST
def verify_payment(request):
    try:
        data = json.loads(request.body)

        booking_id = data.get("booking_id")
        payment_id = data.get("razorpay_payment_id")
        order_id = data.get("razorpay_order_id")
        signature = data.get("razorpay_signature")

        if not all([
            booking_id,
            payment_id,
            order_id,
            signature
        ]):
            return JsonResponse(
                {"error": "Missing payment details."},
                status=400
            )

        client = razorpay_client()

        client.utility.verify_payment_signature({
            "razorpay_order_id": order_id,
            "razorpay_payment_id": payment_id,
            "razorpay_signature": signature
        })

        # Confirm that Razorpay reports a captured payment.
        remote_payment = client.payment.fetch(payment_id)

        if (
            remote_payment.get("order_id") != order_id
            or remote_payment.get("status") != "captured"
        ):
            return JsonResponse(
                {"error": "Payment has not been captured."},
                status=400
            )

        with transaction.atomic():
            booking = get_object_or_404(
                Booking.objects.select_for_update(),
                id=booking_id,
                user=request.user
            )

            payment = get_object_or_404(
                Payment.objects.select_for_update(),
                booking=booking,
                razorpay_order_id=order_id
            )

            if payment.status == "SUCCESS" and booking.status == "CONFIRMED":
                return JsonResponse({
                    "message": "Payment already verified.",
                    "booking_id": booking.id
                })

            if booking.status != "PENDING":
                return JsonResponse(
                    {"error": "Booking is no longer pending."},
                    status=409
                )

            now = timezone.now()

            seats = ShowSeat.objects.select_for_update().filter(
                booking=booking,
                status="RESERVED",
                reserved_until__gt=now
            )

            seat_count = seats.count()

            if seat_count == 0:
                return JsonResponse(
                    {"error": "Reservation expired. Contact support if charged."},
                    status=409
                )

            expected_paise = int(payment.amount * 100)

            if (
                remote_payment.get("amount") != expected_paise
                or remote_payment.get("currency") != "INR"
            ):
                return JsonResponse(
                    {"error": "Payment amount mismatch."},
                    status=400
                )

            payment.razorpay_payment_id = payment_id
            payment.razorpay_signature = signature
            payment.status = "SUCCESS"
            payment.save()

            seats.update(
                status="BOOKED",
                reserved_until=None
            )

            booking.status = "CONFIRMED"
            booking.save(update_fields=["status"])

        return JsonResponse({
            "message": "Payment verified successfully.",
            "booking_id": booking_id
        })

    except (ValueError, TypeError, json.JSONDecodeError):
        return JsonResponse(
            {"error": "Invalid payment request."},
            status=400
        )

    except razorpay.errors.SignatureVerificationError:
        return JsonResponse(
            {"error": "Invalid payment signature."},
            status=400
        )

    except Exception:
        logger.exception("Payment verification failed")
        return JsonResponse(
            {"error": "Unable to verify payment."},
            status=500
        )


@login_required
def booking_confirmation(request, booking_id):
    booking = get_object_or_404(
        Booking.objects.select_related("show__movie"),
        id=booking_id,
        user=request.user,
        status="CONFIRMED"
    )

    seats = ShowSeat.objects.filter(
        booking=booking,
        status="BOOKED"
    ).select_related("seat")

    return render(
        request,
        "payments/confirmation.html",
        {
            "booking": booking,
            "seats": seats
        }
    )
