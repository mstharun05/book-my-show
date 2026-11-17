from django.core.paginator import Paginator
from django.db.models import Avg, Count, Exists, F, OuterRef, Q, Subquery, IntegerField, FloatField
from django.db.models.functions import Coalesce
from django.shortcuts import render
from django.utils import timezone

from movies.models import Movie, Review
from bookings.models import Booking, Show, Theater
from .forms import DiscoveryForm


def filtered_movies(data):
    shows = Show.objects.filter(show_time__gte=timezone.now())
    if data.get("city"):
        shows = shows.filter(screen__theater__city__iexact=data["city"])
    if data.get("theater"):
        shows = shows.filter(screen__theater=data["theater"])
    if data.get("show_from"):
        shows = shows.filter(show_time__gte=data["show_from"])
    if data.get("show_to"):
        shows = shows.filter(show_time__lte=data["show_to"])
    matching_shows = shows.filter(movie_id=OuterRef("pk"))
    ratings = Review.objects.filter(movie_id=OuterRef("pk")).order_by().values(
        "movie_id"
    ).annotate(value=Avg("rating")).values("value")
    popularity = Booking.objects.filter(show__movie_id=OuterRef("pk"), status="CONFIRMED").order_by().values(
        "show__movie_id"
    ).annotate(value=Count("id")).values("value")
    movies = Movie.objects.annotate(
        calculated_rating=Coalesce(Subquery(ratings, output_field=FloatField()),0.0),
        booking_count=Coalesce(Subquery(popularity, output_field=IntegerField()),0),
        minimum_price=Subquery(matching_shows.order_by("ticket_price","pk").values("ticket_price")[:1]),
        next_show_id=Subquery(matching_shows.order_by("show_time","pk").values("pk")[:1]),
    )
    if data.get("search"):
        movies = movies.filter(title__icontains=data["search"])
    if data.get("genre"):
        movies = movies.filter(genre=data["genre"])
    if data.get("language"):
        movies = movies.filter(languages=data["language"])
    if data.get("release_from"):
        movies = movies.filter(release_date__gte=data["release_from"])
    if data.get("release_to"):
        movies = movies.filter(release_date__lte=data["release_to"])
    if data.get("min_rating") is not None:
        movies = movies.filter(calculated_rating__gte=data["min_rating"])
    if any(data.get(key) for key in ("city","theater","show_from","show_to")):
        movies = movies.filter(Exists(matching_shows))
    ordering = {
        "newest": ["-release_date","-pk"],
        "popular": ["-booking_count","-release_date","pk"],
        "rating": ["-calculated_rating","-release_date","pk"],
        "price": [F("minimum_price").asc(nulls_last=True),"pk"],
        "price_desc": [F("minimum_price").desc(nulls_last=True),"pk"],
    }
    return movies.order_by(*ordering.get(data.get("sort"),ordering["newest"])).prefetch_related("genre","languages")


def recommended_movies(request, movies):
    recent = [pk for pk in request.session.get("recent_movies", []) if isinstance(pk, int)][:20]
    booked = []
    if request.user.is_authenticated:
        booked = list(Booking.objects.filter(user=request.user, status="CONFIRMED").order_by(
            "-created_at","-pk"
        ).values_list("show__movie_id",flat=True)[:30])
    seeds = list(dict.fromkeys(recent + booked))
    if not seeds:
        return movies.order_by("-booking_count","-calculated_rating","-release_date","pk")[:6], False
    seed_genres = Movie.genre.through.objects.filter(movie_id__in=seeds).values("genre_id")
    seed_languages = Movie.languages.through.objects.filter(movie_id__in=seeds).values("language_id")
    recommendations = movies.exclude(pk__in=seeds).annotate(
        genre_matches=Count("genre",filter=Q(genre__in=seed_genres),distinct=True),
        language_matches=Count("languages",filter=Q(languages__in=seed_languages),distinct=True),
    ).annotate(affinity=F("genre_matches")*2+F("language_matches")).filter(affinity__gt=0)
    return recommendations.order_by("-affinity","-calculated_rating","-booking_count","pk")[:6], True


def movie_list(request):
    form = DiscoveryForm(request.GET)
    valid = form.is_valid()
    movies = filtered_movies(form.cleaned_data) if valid else Movie.objects.none()
    paginator = Paginator(movies, 8)
    page = paginator.get_page(request.GET.get("page"))
    recommended, personalized = recommended_movies(request, movies) if valid else ([], False)
    query = request.GET.copy()
    query.pop("page", None)
    query.pop("partial", None)
    context = {
        "form":form, "page_obj":page, "matching_count":paginator.count,
        "recommended":recommended, "personalized":personalized, "query":query.urlencode(),
        "search":request.GET.get("search",""),
        "cities": Theater.objects.order_by("city").values_list("city",flat=True).distinct(),
    }
    template = "discovery/results.html" if request.GET.get("partial") == "1" else "discovery/movie_list.html"
    return render(request,template,context)
