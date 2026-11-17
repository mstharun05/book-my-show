from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from bookings.models import Booking, Screen, Seat, Show, ShowSeat, Theater

from .models import Movie, Review


class ReviewEligibilityTests(TestCase):
    def test_review_requires_confirmed_attendance_and_a_finished_show(self):
        viewer = User.objects.create_user("viewer")
        self.client.force_login(viewer)
        now = timezone.now()
        movie = Movie.objects.create(
            title="Test Film", duration=120, release_date=timezone.localdate(),
        )
        theater = Theater.objects.create(name="Cinema", city="Salem")
        screen = Screen.objects.create(theater=theater, name="1")
        seat = Seat.objects.create(screen=screen, seat_number="A1")
        show = Show.objects.create(
            movie=movie, screen=screen, show_time=now - timedelta(minutes=30),
            ticket_price=100,
        )
        booking = Booking.objects.create(user=viewer, show=show, status="CONFIRMED")
        ShowSeat.objects.create(show=show, seat=seat, booking=booking, status="BOOKED")
        endpoint = reverse("movies:submit_review", args=[movie.pk])
        self.client.post(endpoint, {"rating": 4, "comment": "Good"})
        booking.attended_at = now
        booking.save(update_fields=["attended_at"])
        self.client.post(endpoint, {"rating": 4, "comment": "Good"})
        self.assertFalse(Review.objects.exists())

        show.show_time = now - timedelta(hours=3)
        show.save(update_fields=["show_time"])
        booking.attended_at = None
        booking.save(update_fields=["attended_at"])
        self.client.post(endpoint, {"rating": 4, "comment": "Good"})
        self.assertFalse(Review.objects.exists())

        booking.attended_at = now
        booking.save(update_fields=["attended_at"])
        self.client.post(endpoint, {"rating": 4, "comment": "Good"})
        self.client.post(endpoint, {"rating": 5, "comment": "Great"})
        review = Review.objects.get()
        self.assertTrue(review.verified_viewer)
        self.assertEqual(review.comment, "Great")
        self.assertEqual(movie.average_rating, 5)

        response = self.client.get(reverse("discovery:movie_detail", args=[movie.pk]))
        self.assertContains(response, "Verified Viewer")
        self.assertContains(response, "Edit Your Review")

    def test_trailer_uses_only_a_validated_video_id(self):
        movie = Movie(trailer_url="https://youtu.be/dQw4w9WgXcQ?si=extra")
        self.assertEqual(
            movie.trailer_embed_url,
            "https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ",
        )
        movie.trailer_url = "https://youtube.com.example.org/watch?v=dQw4w9WgXcQ"
        self.assertEqual(movie.trailer_embed_url, "")
