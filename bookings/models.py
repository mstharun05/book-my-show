
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
from movies.models import Movie


class Theater(models.Model):
    name = models.CharField(max_length=150)
    city = models.CharField(max_length=100)
    address = models.TextField()

    def __str__(self):
        return self.name


class Screen(models.Model):
    theater = models.ForeignKey(Theater, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.theater.name} - {self.name}"


class Seat(models.Model):
    screen = models.ForeignKey(Screen, on_delete=models.CASCADE)
    seat_number = models.CharField(max_length=10)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['screen', 'seat_number'],
                name='unique_screen_seat'
            )
        ]

    def __str__(self):
        return self.seat_number


class Show(models.Model):
    movie = models.ForeignKey(Movie, on_delete=models.CASCADE)
    screen = models.ForeignKey(Screen, on_delete=models.CASCADE)
    show_time = models.DateTimeField()
    ticket_price = models.DecimalField(max_digits=8, decimal_places=2)

    def __str__(self):
        return f"{self.movie.title} - {self.show_time}"


class Booking(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('CONFIRMED', 'Confirmed'),
        ('CANCELLED', 'Cancelled'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    show = models.ForeignKey(Show, on_delete=models.CASCADE)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='PENDING'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Booking #{self.id}"


class ShowSeat(models.Model):
    STATUS_CHOICES = [
        ('AVAILABLE', 'Available'),
        ('RESERVED', 'Reserved'),
        ('BOOKED', 'Booked'),
    ]

    show = models.ForeignKey(Show, on_delete=models.CASCADE)
    seat = models.ForeignKey(Seat, on_delete=models.CASCADE)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='AVAILABLE'
    )
    reserved_until = models.DateTimeField(null=True, blank=True)
    booking = models.ForeignKey(
        Booking, on_delete=models.SET_NULL, null=True, blank=True
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['show', 'seat'],
                name='unique_seat_per_show'
            )
        ]

    def __str__(self):
        return f"{self.show} - {self.seat}"
