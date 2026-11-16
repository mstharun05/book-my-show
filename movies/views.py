
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import Movie, Review
from bookings.models import Booking, ShowSeat


def can_review_movie(user, movie):
    if not user.is_authenticated:
        return False

    return Booking.objects.filter(
        user=user,
        show__movie=movie,
        show__show_time__lt=timezone.now(),
        status="CONFIRMED",
        showseat__status="BOOKED"
    ).exists()


def movie_detail(request, movie_id):
    movie = get_object_or_404(Movie, id=movie_id)

    reviews = movie.reviews.select_related("user").order_by("-created_at")

    similar_movies = (
        Movie.objects.filter(
            Q(genre__in=movie.genre.all()) |
            Q(languages__in=movie.languages.all())
        )
        .exclude(id=movie.id)
        .distinct()[:6]
    )

    trending_movies = (
        Movie.objects.annotate(
            booking_count=Count(
                "show__booking",
                filter=Q(show__booking__status="CONFIRMED"),
                distinct=True
            )
        )
        .order_by("-booking_count", "-release_date")[:6]
    )

    recent_movies = Movie.objects.filter(
        release_date__lte=timezone.localdate()
    ).order_by("-release_date")[:6]

    user_review = None
    eligible = can_review_movie(request.user, movie)

    if request.user.is_authenticated:
        user_review = Review.objects.filter(
            movie=movie,
            user=request.user
        ).first()

    return render(
        request,
        "movies/movie_detail.html",
        {
            "movie": movie,
            "reviews": reviews,
            "similar_movies": similar_movies,
            "trending_movies": trending_movies,
            "recent_movies": recent_movies,
            "can_review": eligible,
            "user_review": user_review,
        }
    )


@login_required
@require_POST
def submit_review(request, movie_id):
    movie = get_object_or_404(Movie, id=movie_id)

    if not can_review_movie(request.user, movie):
        messages.error(
            request,
            "You can review only after booking and watching this movie."
        )
        return redirect("movies:movie_detail", movie_id=movie.id)

    try:
        rating = int(request.POST.get("rating", 0))
    except (ValueError, TypeError):
        rating = 0

    comment = request.POST.get("comment", "").strip()

    if rating < 1 or rating > 5 or not comment:
        messages.error(request, "Enter a rating from 1 to 5 and a comment.")
        return redirect("movies:movie_detail", movie_id=movie.id)

    Review.objects.update_or_create(
        movie=movie,
        user=request.user,
        defaults={
            "rating": rating,
            "comment": comment,
            "verified_viewer": True
        }
    )

    messages.success(request, "Review saved successfully.")
    return redirect("movies:movie_detail", movie_id=movie.id)


@login_required
@require_POST
def report_review(request, review_id):
    review = get_object_or_404(Review, id=review_id)

    if review.user_id == request.user.id:
        messages.error(request, "You cannot report your own review.")
    else:
        review.reported = True
        review.save(update_fields=["reported"])
        messages.success(request, "Review reported successfully.")

    return redirect("movies:movie_detail", movie_id=review.movie_id)
