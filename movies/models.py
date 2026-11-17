
import re
from urllib.parse import urlparse, parse_qs

from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db.models import Avg


class Genre(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name


class Language(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name


class CastMember(models.Model):
    name = models.CharField(max_length=150)
    biography = models.TextField(blank=True)
    photo = models.URLField(blank=True)

    def __str__(self):
        return self.name


class Movie(models.Model):
    AGE_CHOICES = [
        ("U", "U"),
        ("UA", "UA"),
        ("A", "A"),
        ("S", "S"),
    ]

    title = models.CharField(max_length=200)
    description = models.TextField()

    genre = models.ManyToManyField(Genre)
    languages = models.ManyToManyField(Language)
    cast = models.ManyToManyField(CastMember, blank=True)

    trailer_url = models.URLField(blank=True)
    poster = models.URLField(blank=True)

    age_certificate = models.CharField(
        max_length=5,
        choices=AGE_CHOICES,
        default="U"
    )

    duration = models.PositiveIntegerField(
        help_text="Duration in minutes"
    )

    release_date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["release_date", "id"], name="movie_release_idx")]

    @property
    def average_rating(self):
        result = self.reviews.aggregate(
            average=Avg("rating")
        )["average"]

        return round(result or 0, 1)

    def clean(self):
        super().clean()
        if self.trailer_url and not self.trailer_embed_url:
            raise ValidationError({"trailer_url": "Enter a valid YouTube video URL."})

    @property
    def trailer_embed_url(self):
        if not self.trailer_url:
            return ""

        try:
            parsed = urlparse(self.trailer_url)
            host = parsed.hostname
            if parsed.username is not None or parsed.port is not None:
                return ""
        except ValueError:
            return ""
        video_id = ""

        if parsed.scheme not in ("http", "https"):
            return ""

        if host in (
            "youtube.com",
            "www.youtube.com",
            "m.youtube.com",
            "www.youtube-nocookie.com",
            "youtube-nocookie.com",
        ):
            if parsed.path == "/watch":
                video_id = parse_qs(
                    parsed.query
                ).get("v", [""])[0]

            elif parsed.path.startswith(("/embed/", "/shorts/")):
                parts = parsed.path.strip("/").split("/")
                if len(parts) == 2:
                    video_id = parts[1]

        elif host in ("youtu.be", "www.youtu.be"):
            video_id = parsed.path.strip("/")

        if not re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id):
            return ""

        return (
            "https://www.youtube-nocookie.com/embed/"
            f"{video_id}"
        )

    def __str__(self):
        return self.title


class PosterImage(models.Model):
    movie = models.ForeignKey(
        Movie,
        on_delete=models.CASCADE,
        related_name="posters"
    )

    image_url = models.URLField()

    def __str__(self):
        return f"{self.movie.title} - Poster #{self.pk}"


class Review(models.Model):
    movie = models.ForeignKey(
        Movie,
        on_delete=models.CASCADE,
        related_name="reviews"
    )

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE
    )

    rating = models.PositiveSmallIntegerField(
        validators=[
            MinValueValidator(1),
            MaxValueValidator(5)
        ]
    )

    comment = models.TextField()

    verified_viewer = models.BooleanField(default=False)
    reported = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["movie", "user"],
                name="one_review_per_movie_user"
            )
        ]

    def __str__(self):
        return (
            f"{self.user.username} - "
            f"{self.movie.title} ({self.rating}/5)"
        )
