
from django.shortcuts import render, get_object_or_404
from django.db.models import Q, Avg, Count, Prefetch
from django.core.paginator import Paginator
from django.utils import timezone

from movies.models import Movie, Genre, Language
from bookings.models import Show


def movie_list(request):

    search = request.GET.get("search", "").strip()
    selected_genre = request.GET.get("genre", "").strip()
    selected_language = request.GET.get("language", "").strip()
    selected_sort = request.GET.get("sort", "newest").strip()

    movies = Movie.objects.all()

    # Search movies
    if search:
        movies = movies.filter(
            Q(title__icontains=search) |
            Q(description__icontains=search)
        )

    # Filter by genre ID
    if selected_genre:
        movies = movies.filter(genre__id=selected_genre)

    # Filter by language ID
    if selected_language:
        movies = movies.filter(languages__id=selected_language)

    # Avoid conflict with Movie.average_rating property
    movies = movies.annotate(
        calculated_rating=Avg("reviews__rating"),
        booking_count=Count(
            "show__booking",
            filter=Q(show__booking__status="CONFIRMED"),
            distinct=True
        )
    ).distinct()

    # Sorting
    if selected_sort == "rating":
        movies = movies.order_by(
            "-calculated_rating",
            "-release_date"
        )

    elif selected_sort == "popular":
        movies = movies.order_by(
            "-booking_count",
            "-release_date"
        )

    else:
        selected_sort = "newest"
        movies = movies.order_by(
            "-release_date",
            "-created_at"
        )

    # Load movie genres, languages and upcoming shows
    movies = movies.prefetch_related(
        "genre",
        "languages",
        Prefetch(
            "show_set",
            queryset=Show.objects.filter(
                show_time__gte=timezone.now()
            ).order_by("show_time"),
            to_attr="upcoming_shows"
        )
    )

    # Pagination
    matching_count = movies.count()
    paginator = Paginator(movies, 8)
    page_obj = paginator.get_page(
        request.GET.get("page")
    )

    context = {
        "page_obj": page_obj,
        "movies": page_obj,
        "matching_count": matching_count,
        "genres": Genre.objects.all().order_by("name"),
        "languages": Language.objects.all().order_by("name"),
        "search": search,
        "selected_genre": selected_genre,
        "selected_language": selected_language,
        "selected_sort": selected_sort,
    }

    return render(
        request,
        "discovery/movie_list.html",
        context
    )
