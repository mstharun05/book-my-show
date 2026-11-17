from django.db import models
from django.core.validators import MinValueValidator, URLValidator


class Experience(models.Model):
    class Category(models.TextChoices):
        EVENTS = 'events', 'Events'
        PLAYS = 'plays', 'Plays'
        SPORTS = 'sports', 'Sports'
        ACTIVITIES = 'activities', 'Activities'

    category = models.CharField(max_length=12, choices=Category.choices)
    title = models.CharField(max_length=200)
    description = models.TextField()
    city = models.CharField(max_length=100)
    venue = models.CharField(max_length=200)
    address = models.TextField(blank=True)
    starts_at = models.DateTimeField()
    duration_minutes = models.PositiveIntegerField(default=60, validators=[MinValueValidator(1)])
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0, validators=[MinValueValidator(0)])
    poster = models.URLField(blank=True, validators=[URLValidator(schemes=['https'])])
    booking_url = models.URLField(blank=True, validators=[URLValidator(schemes=['https'])], help_text='Official organizer HTTPS booking URL. Leave blank when bookings are not open.')
    published = models.BooleanField(default=False)

    class Meta:
        indexes = [models.Index(fields=['category', 'published', 'starts_at'])]
        ordering = ['starts_at', 'pk']

    def __str__(self):
        return self.title

# Create your models here.
