from datetime import timedelta
from decimal import Decimal
from django.contrib.auth.models import User, Permission
from django.test import TestCase
from django.utils import timezone
from bookings.models import Booking, Show, Seat, ShowSeat, Screen, Theater
from movies.models import Movie
from payments.models import Payment
from .analytics import analytics


class DashboardTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("analyst", is_staff=True)
        self.user.user_permissions.add(Permission.objects.get(codename="view_business_dashboard"))
        movie = Movie.objects.create(title="Film", duration=100, release_date=timezone.localdate())
        theater = Theater.objects.create(name="Cinema", city="City")
        screen = Screen.objects.create(theater=theater, name="Screen")
        seat = Seat.objects.create(screen=screen, seat_number="A1")
        Seat.objects.create(screen=screen, seat_number="A2")
        self.show = Show.objects.create(movie=movie, screen=screen, show_time=timezone.now(), ticket_price=200)
        self.booking = Booking.objects.create(user=self.user, show=self.show, status="CONFIRMED")
        ShowSeat.objects.create(show=self.show, seat=seat, booking=self.booking, status="BOOKED")
        Payment.objects.create(booking=self.booking, amount=200, status="SUCCESS", razorpay_order_id="test")

    def test_aggregates_and_occupancy(self):
        today = timezone.localdate()
        data = analytics(today,today)
        self.assertEqual(data["totals"]["revenue"], Decimal("200"))
        self.assertEqual(data["booking_totals"]["confirmed"],1)
        self.assertEqual(data["occupancy"][0]["percentage"],50)
        self.assertEqual(data["occupancy"][0]["capacity"],2)
        self.assertEqual(data["new_users"],1)

    def test_permissions_and_exports(self):
        self.assertEqual(self.client.get("/dashboard/data/").status_code,302)
        other = User.objects.create_user("staff",is_staff=True)
        self.client.force_login(other)
        for url in ("/dashboard/","/dashboard/data/","/dashboard/export/"):
            self.assertEqual(self.client.get(url).status_code,403)
        self.client.force_login(self.user)
        self.assertEqual(self.client.get("/dashboard/data/").status_code,200)
        response=self.client.get("/dashboard/export/?type=bookings")
        self.assertIn(b"Film", b"".join(response.streaming_content))
        self.assertEqual(self.client.get("/dashboard/?start=2026-11-20&end=2026-11-01").status_code,400)

    def test_range_boundaries(self):
        yesterday = timezone.localdate()-timedelta(days=1)
        data=analytics(yesterday,yesterday)
        self.assertEqual(data["booking_totals"]["total"],0)
        self.assertEqual(data["totals"]["revenue"],0)
