import hashlib
import hmac
from datetime import timedelta
from unittest.mock import patch

import razorpay
from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.utils import timezone

from bookings.models import Theater, Screen, Seat, Show
from bookings.services import reserve_seats
from movies.models import Movie
from .models import Payment


@override_settings(RAZORPAY_KEY_ID="rzp_test_local", RAZORPAY_KEY_SECRET="local-test-secret")
class PaymentVerificationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("buyer")
        self.client.force_login(self.user)
        movie = Movie.objects.create(title="Film", duration=120, release_date=timezone.localdate())
        theater = Theater.objects.create(name="Cinema", city="City")
        screen = Screen.objects.create(theater=theater, name="Screen")
        seat = Seat.objects.create(screen=screen, seat_number="1")
        show = Show.objects.create(movie=movie, screen=screen, ticket_price=200, show_time=timezone.now()+timedelta(days=1))
        self.booking = reserve_seats(self.user, show.pk, [seat.pk])
        self.sdk = razorpay.Client(auth=("rzp_test_local", "local-test-secret"))
        self.client_patch = patch("payments.views.razorpay_client", return_value=self.sdk)
        self.client_patch.start()
        self.addCleanup(self.client_patch.stop)
        self.order_patch = patch.object(self.sdk.order, "create", return_value={"id": "order_test"})
        self.order_create = self.order_patch.start()
        self.addCleanup(self.order_patch.stop)
        self.remote = {"id":"pay_test", "order_id":"order_test", "status":"captured", "amount":20000, "currency":"INR"}
        self.fetch_patch = patch.object(self.sdk.payment, "fetch", side_effect=lambda _: self.remote)
        self.fetch_patch.start()
        self.addCleanup(self.fetch_patch.stop)
        response = self.client.post(f"/payments/create/{self.booking.pk}/")
        self.assertEqual(response.status_code, 200)
        signature = hmac.new(b"local-test-secret", b"order_test|pay_test", hashlib.sha256).hexdigest()
        self.payload = dict(booking_id=self.booking.pk, razorpay_order_id="order_test",
                            razorpay_payment_id="pay_test", razorpay_signature=signature)

    def verify(self):
        return self.client.post("/payments/verify/", self.payload, content_type="application/json")

    def test_success_and_duplicate_callback(self):
        self.assertEqual(self.verify().status_code, 200)
        self.assertEqual(self.verify().status_code, 200)
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.status, "CONFIRMED")
        self.assertEqual(self.booking.showseat_set.get().status, "BOOKED")
        self.assertEqual(Payment.objects.get().status, "SUCCESS")
        self.assertEqual(self.client.get(f"/payments/confirmation/{self.booking.pk}/").status_code, 200)

    def test_order_creation_reuses_order(self):
        self.assertEqual(self.client.post(f"/payments/create/{self.booking.pk}/").status_code, 200)
        self.assertEqual(self.order_create.call_count, 1)

    def test_invalid_signature(self):
        self.payload["razorpay_signature"] = "invalid"
        self.assertEqual(self.verify().status_code, 400)
        self.assertEqual(Payment.objects.get().status, "CREATED")

    def test_wrong_amount_or_uncaptured_payment(self):
        self.remote["amount"] = 1
        self.assertEqual(self.verify().status_code, 400)
        self.remote["amount"] = 20000
        self.remote["status"] = "authorized"
        self.assertEqual(self.verify().status_code, 400)

    def test_expired_hold_cannot_confirm(self):
        self.booking.showseat_set.update(reserved_until=timezone.now()-timedelta(seconds=1))
        self.assertEqual(self.verify().status_code, 409)
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.status, "CANCELLED")

    def test_other_user_cannot_confirm(self):
        self.client.force_login(User.objects.create_user("other"))
        self.assertEqual(self.verify().status_code, 404)

    def test_invalid_payload(self):
        self.assertEqual(self.client.post("/payments/verify/", [], content_type="application/json").status_code, 400)

    @override_settings(RAZORPAY_WEBHOOK_SECRET="webhook-test-secret")
    def send_webhook(self, entity, signature_valid=True):
        import json
        body = json.dumps({"event": "payment." + entity["status"], "payload": {"payment": {"entity": entity}}})
        signature = hmac.new(b"webhook-test-secret", body.encode(), hashlib.sha256).hexdigest()
        if not signature_valid:
            signature = "invalid"
        return self.client.post("/payments/webhook/", body, content_type="application/json",
                                HTTP_X_RAZORPAY_SIGNATURE=signature)

    def test_webhook_signature_and_duplicate_capture(self):
        self.assertEqual(self.send_webhook(self.remote, False).status_code, 400)
        self.assertEqual(self.send_webhook(self.remote).status_code, 200)
        self.assertEqual(self.send_webhook(self.remote).status_code, 200)
        self.assertEqual(self.verify().status_code, 200)
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.status, "CONFIRMED")
        self.assertEqual(Payment.objects.get().attempts.count(), 1)

    def test_failed_webhook_releases_seats_and_records_transaction(self):
        self.remote["status"] = "failed"
        self.assertEqual(self.send_webhook(self.remote).status_code, 200)
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.status, "CANCELLED")
        self.assertFalse(self.booking.showseat_set.exists())
        self.assertEqual(Payment.objects.get().attempts.get().transaction_id, "pay_test")

    def test_cancel_then_late_capture_requires_refund(self):
        response = self.client.post(f"/payments/cancel/{self.booking.pk}/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.send_webhook(self.remote).status_code, 200)
        payment = Payment.objects.get()
        self.assertEqual(payment.status, "REFUND_REQUIRED")
        self.assertEqual(payment.attempts.get().status, "REFUND_REQUIRED")
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.status, "CANCELLED")

    def test_failed_event_cannot_undo_success(self):
        self.verify()
        self.remote["status"] = "failed"
        self.send_webhook(self.remote)
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.status, "CONFIRMED")
        self.assertEqual(Payment.objects.get().status, "SUCCESS")

    def test_history_is_private_and_shows_transaction(self):
        self.verify()
        response = self.client.get("/payments/history/")
        self.assertContains(response, "pay_test")
        self.client.force_login(User.objects.create_user("stranger"))
        self.assertNotContains(self.client.get("/payments/history/"), "pay_test")

    def test_retry_reacquires_released_seat(self):
        seat_id = self.booking.showseat_set.get().seat_id
        self.remote["status"] = "failed"
        self.send_webhook(self.remote)
        retry = reserve_seats(self.user, self.booking.show_id, [seat_id])
        self.assertNotEqual(retry.pk, self.booking.pk)
        self.assertEqual(retry.status, "PENDING")
        self.assertEqual(retry.showseat_set.count(), 1)
