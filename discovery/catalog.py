from django.core.paginator import Paginator
from django.http import Http404
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from movies.models import Movie
from .models import Experience

CATEGORIES = dict(Experience.Category.choices)


def category(request, category):
    if category != 'stream' and category not in CATEGORIES:
        raise Http404
    search = request.GET.get('q', '').strip()[:200]
    city = request.GET.get('city', '').strip()[:100]
    if category == 'stream':
        items = Movie.objects.exclude(trailer_url='').order_by('-release_date', '-pk')
    else:
        items = Experience.objects.filter(category=category, published=True, starts_at__gte=timezone.now()).order_by('starts_at', 'pk')
        if city:
            items = items.filter(city__icontains=city)
    if search:
        items = items.filter(title__icontains=search)
    page = Paginator(items, 12).get_page(request.GET.get('page'))
    query = request.GET.copy()
    query.pop('page', None)
    return render(request, 'discovery/category.html', {
        'category': category, 'category_title': CATEGORIES.get(category, 'Stream'),
        'page': page, 'q': search, 'city': city, 'query': query.urlencode(),
    })


def experience_detail(request, pk):
    item = get_object_or_404(Experience, pk=pk, published=True)
    return render(request, 'discovery/experience_detail.html', {'item': item, 'category': item.category, 'upcoming': item.starts_at >= timezone.now()})
