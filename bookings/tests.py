from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier

from django.contrib.auth.models import User
from django.db import close_old_connections
from django.test import TransactionTestCase
from django.utils import timezone

from .models import Booking, Screen, Seat, Show, ShowSeat, Theater
from .services import reserve_seats, release_expired_seats, SeatUnavailableError
from movies.models import Movie


class ReservationTests(TransactionTestCase):
    def setUp(self):
        self.users = [User.objects.create_user("one"), User.objects.create_user("two")]
        movie = Movie.objects.create(title="Film", duration=90, release_date=timezone.localdate())
        theater = Theater.objects.create(name="Cinema", city="City")
        screen = Screen.objects.create(theater=theater, name="Screen")
        self.seats = [Seat.objects.create(screen=screen, seat_number=str(n)) for n in range(3)]
        self.show = Show.objects.create(movie=movie, screen=screen, show_time=timezone.now() + timedelta(days=1), ticket_price=100)

    def test_competing_requests_cannot_book_same_seat(self):
        barrier = Barrier(2)
        def reserve(user):
            close_old_connections()
            barrier.wait()
            try:
                reserve_seats(user, self.show.pk, [self.seats[0].pk])
                return "reserved"
            except SeatUnavailableError:
                return "conflict"
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(reserve, self.users))
        self.assertCountEqual(results, ["reserved", "conflict"])
        self.assertEqual(Booking.objects.filter(status="PENDING").count(), 1)

    def test_change_is_atomic_and_keeps_expiry(self):
        first = reserve_seats(self.users[0], self.show.pk, [self.seats[0].pk])
        expiry = first.showseat_set.get().reserved_until
        reserve_seats(self.users[1], self.show.pk, [self.seats[1].pk])
        with self.assertRaises(SeatUnavailableError):
            reserve_seats(self.users[0], self.show.pk, [self.seats[1].pk], first.pk)
        self.assertEqual(first.showseat_set.count(), 1)
        changed = reserve_seats(self.users[0], self.show.pk, [self.seats[2].pk], first.pk)
        first.refresh_from_db()
        self.assertEqual(first.status, "CANCELLED")
        self.assertEqual(changed.showseat_set.get().reserved_until, expiry)
        self.assertEqual(ShowSeat.objects.get(show=self.show, seat=self.seats[0]).status, "AVAILABLE")

    def test_expiry_releases_and_cancels(self):
        booking = reserve_seats(self.users[0], self.show.pk, [self.seats[0].pk])
        booking.showseat_set.update(reserved_until=timezone.now() - timedelta(seconds=1))
        release_expired_seats(self.show.pk)
        booking.refresh_from_db()
        self.assertEqual(booking.status, "CANCELLED")
        replacement = reserve_seats(self.users[1], self.show.pk, [self.seats[0].pk])
        self.assertEqual(replacement.showseat_set.count(), 1)

    def test_concurrent_payment_confirmations_are_idempotent(self):
        from payments.models import Payment, PaymentAttempt
        from payments.services import apply_payment
        booking = reserve_seats(self.users[0], self.show.pk, [self.seats[0].pk])
        Payment.objects.create(booking=booking, amount=100, razorpay_order_id="order_concurrent")
        entity = {"id":"pay_concurrent", "order_id":"order_concurrent",
                  "status":"captured", "amount":10000, "currency":"INR"}
        barrier = Barrier(2)
        def confirm(_):
            close_old_connections()
            barrier.wait()
            try:
                return apply_payment(entity).status
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(confirm, range(2)))
        self.assertEqual(results, ["SUCCESS", "SUCCESS"])
        self.assertEqual(PaymentAttempt.objects.count(), 1)
        self.assertEqual(Booking.objects.filter(status="CONFIRMED").count(), 1)
