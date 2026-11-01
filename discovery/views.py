
from django.shortcuts import render
from django.db.models import Avg, Count, Q
from django.core.paginator import Paginator
from movies.models import Movie, Genre, Language


def movie_list(request):

    movies = Movie.objects.annotate(
        average_rating=Avg('reviews__rating'),
        popularity=Count('reviews')
    ).distinct()

    search = request.GET.get('search', '')
    genre = request.GET.get('genre', '')
    language = request.GET.get('language', '')
    sorting = request.GET.get('sort', 'newest')

    if search:
        movies = movies.filter(title__icontains=search)

    if genre:
        movies = movies.filter(genre__id=genre)

    if language:
        movies = movies.filter(languages__id=language)

    if sorting == 'rating':
        movies = movies.order_by('-average_rating')

    elif sorting == 'popular':
        movies = movies.order_by('-popularity')

    elif sorting == 'newest':
        movies = movies.order_by('-release_date')

    paginator = Paginator(movies, 6)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'discovery/movie_list.html', {
        'page_obj': page_obj,
        'genres': Genre.objects.all(),
        'languages': Language.objects.all(),
        'search': search,
        'selected_genre': genre,
        'selected_language': language,
        'selected_sort': sorting,
        'matching_count': paginator.count,
    })
