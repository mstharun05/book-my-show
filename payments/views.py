
import hashlib
import hmac
import json
import logging
import ssl
from decimal import Decimal

import razorpay
import requests

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.core.paginator import Paginator
from django.utils import timezone

from bookings.models import Booking, ShowSeat
from bookings.services import lock_show
from .models import Payment
from .services import apply_payment, cancel_booking


logger = logging.getLogger(__name__)


class SystemTrustAdapter(requests.adapters.HTTPAdapter):
    def init_poolmanager(self, *args, **kwargs):
        kwargs["ssl_context"] = ssl.create_default_context()
        return super().init_poolmanager(*args, **kwargs)


def razorpay_client():
    key_id = getattr(settings, "RAZORPAY_KEY_ID", "")
    key_secret = getattr(settings, "RAZORPAY_KEY_SECRET", "")

    if not key_id or not key_secret:
        raise ValueError(
            "Razorpay test keys are missing. Configure "
            "RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET."
        )

    session = requests.Session()
    session.mount("https://", SystemTrustAdapter())
    return razorpay.Client(session=session, auth=(key_id, key_secret))


@login_required
@require_POST
def create_payment_order(request, booking_id):
    booking = get_object_or_404(
        Booking,
        id=booking_id,
        user=request.user
    )

    with transaction.atomic():
        lock_show(booking.show_id)
        booking.refresh_from_db()
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
            Payment.objects.create(booking=booking, amount=amount, status="FAILED")
            cancel_booking(booking.pk)
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

        if not isinstance(data, dict):
            raise ValueError("Expected a JSON object.")
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

        owned_booking = get_object_or_404(Booking, pk=booking_id, user=request.user)
        stored_payment = get_object_or_404(
            Payment, booking=owned_booking, razorpay_order_id=order_id
        )
        client = razorpay_client()

        client.utility.verify_payment_signature({
            "razorpay_order_id": stored_payment.razorpay_order_id,
            "razorpay_payment_id": payment_id,
            "razorpay_signature": signature
        })

        remote_payment = client.payment.fetch(payment_id)
        if remote_payment.get("order_id") != order_id or remote_payment.get("id") != payment_id:
            raise ValueError("Payment does not match the order.")
        payment = apply_payment(remote_payment)
        if payment.status != "SUCCESS":
            return JsonResponse(
                {"error": "Payment not confirmed. Check your payment history.", "status": payment.status},
                status=409 if payment.status == "REFUND_REQUIRED" else 400,
            )
        return JsonResponse({"message": "Payment verified.", "booking_id": booking_id})

    except Http404:
        raise

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
        "payments/booking_confirmation.html",
        {
            "booking": booking,
            "seats": seats
        }
    )


@csrf_exempt
@require_POST
def webhook(request):
    secret = settings.RAZORPAY_WEBHOOK_SECRET
    if not secret:
        return JsonResponse({"error": "Webhook secret is not configured."}, status=503)
    expected = hmac.new(secret.encode(), request.body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, request.headers.get("X-Razorpay-Signature", "")):
        return JsonResponse({"error": "Invalid webhook signature."}, status=400)
    try:
        event = json.loads(request.body)
        if event.get("event") not in ("payment.captured", "payment.failed", "payment.authorized", "order.paid"):
            return JsonResponse({"received": True})
        entity = event["payload"]["payment"]["entity"]
        apply_payment(entity)
    except Payment.DoesNotExist:
        return JsonResponse({"error": "Order not registered yet."}, status=503)
    except (ValueError, KeyError, TypeError, AttributeError):
        return JsonResponse({"error": "Invalid webhook payload."}, status=400)
    return JsonResponse({"received": True})


@login_required
@require_POST
def cancel_payment(request, booking_id):
    booking = get_object_or_404(Booking, pk=booking_id, user=request.user)
    # A cancellation requests release, never asserts that money was not captured.
    # Late captures are recorded for refund review by apply_payment.
    booking = cancel_booking(booking.pk)
    return JsonResponse({"booking_id": booking.pk, "status": booking.status})


@login_required
@require_POST
def payment_failed(request, booking_id):
    booking = get_object_or_404(Booking, pk=booking_id, user=request.user)
    try:
        data = json.loads(request.body)
        entity = razorpay_client().payment.fetch(data["payment_id"])
        get_object_or_404(Payment, booking=booking, razorpay_order_id=entity["order_id"])
        payment = apply_payment(entity)
        return JsonResponse({"status": payment.status})
    except (ValueError, KeyError, TypeError):
        return JsonResponse({"error": "Invalid failure notification."}, status=400)
    except Http404:
        raise
    except Exception:
        logger.exception("Payment reconciliation failed")
        return JsonResponse({"error": "Unable to check payment. Please retry."}, status=503)


@login_required
def history(request):
    bookings = Booking.objects.filter(user=request.user).select_related(
        "show__movie", "show__screen__theater"
    ).prefetch_related("payments__attempts").order_by("-created_at", "-pk")
    return render(request, "payments/history.html", {
        "page": Paginator(bookings, 15).get_page(request.GET.get("page"))
    })
