
from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator


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
        ('U', 'U'),
        ('UA', 'UA'),
        ('A', 'A'),
        ('S', 'S'),
    ]

    title = models.CharField(max_length=200)
    description = models.TextField()
    genre = models.ManyToManyField(Genre)
    languages = models.ManyToManyField(Language)
    cast = models.ManyToManyField(CastMember, blank=True)
    trailer_url = models.URLField(blank=True)
    poster = models.URLField(blank=True)
    age_certificate = models.CharField(
        max_length=5, choices=AGE_CHOICES, default='U'
    )
    duration = models.PositiveIntegerField(help_text="Duration in minutes")
    release_date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


class PosterImage(models.Model):
    movie = models.ForeignKey(
        Movie, on_delete=models.CASCADE, related_name='posters'
    )
    image_url = models.URLField()

    def __str__(self):
        return self.movie.title


class Review(models.Model):
    movie = models.ForeignKey(
        Movie, on_delete=models.CASCADE, related_name='reviews'
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    comment = models.TextField()
    verified_viewer = models.BooleanField(default=False)
    reported = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['movie', 'user'],
                name='one_review_per_movie_user'
            )
        ]

    def __str__(self):
        return f"{self.user.username} - {self.movie.title}"
