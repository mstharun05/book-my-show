from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
from django.http import HttpResponseBadRequest
from django.shortcuts import redirect
from django.views.decorators.http import require_POST
from django.utils.http import url_has_allowed_host_and_scheme
from bookings.models import Theater
from .models import Experience

POPULAR_CITIES = [
    ('Mumbai', 19.076, 72.878), ('Delhi-NCR', 28.614, 77.209),
    ('Bengaluru', 12.972, 77.595), ('Hyderabad', 17.385, 78.487),
    ('Chandigarh', 30.733, 76.779), ('Ahmedabad', 23.023, 72.572),
    ('Pune', 18.520, 73.857), ('Chennai', 13.083, 80.271),
    ('Kolkata', 22.573, 88.364), ('Kochi', 9.931, 76.267), ('Salem', 11.665, 78.146),
]


def city_options():
    listed = set(Theater.objects.values_list('city', flat=True).distinct())
    listed.update(Experience.objects.filter(published=True).values_list('city', flat=True).distinct())
    popular = [name for name, _, _ in POPULAR_CITIES]
    return popular + sorted(city for city in listed if city and city not in popular)


def location_context(request):
    return {'selected_city': request.session.get('selected_city', ''),
            'city_options': city_options(), 'city_coordinates': POPULAR_CITIES}


@require_POST
def select_city(request):
    city = request.POST.get('city', '').strip()
    if city and city not in city_options():
        return HttpResponseBadRequest('Choose a city from the list.')
    request.session['selected_city'] = city
    destination = request.POST.get('next', '/movies/')
    if not url_has_allowed_host_and_scheme(destination, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        destination = '/movies/'
    parts = urlsplit(destination)
    query = [(k, v) for k, v in parse_qsl(parts.query) if k not in ('city', 'page', 'partial')]
    if city:
        query.append(('city', city))
    return redirect(urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), '')))
