from datetime import timedelta
from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from bookings.models import Booking, Show, Screen, Theater
from movies.models import Movie, Genre, Language, Review


class DiscoveryTests(TestCase):
    def setUp(self):
        self.movie = Movie.objects.create(title="Space & Time", duration=120, release_date=timezone.localdate())
        self.other = Movie.objects.create(title="Another", duration=90, release_date=timezone.localdate())
        genre=Genre.objects.create(name="Sci-Fi")
        language=Language.objects.create(name="English")
        for movie in (self.movie,self.other):
            movie.genre.add(genre)
            movie.languages.add(language)
        first=Theater.objects.create(name="First",city="Vellore")
        second=Theater.objects.create(name="Second",city="Salem")
        self.theater=second
        screen=Screen.objects.create(theater=first,name="1")
        screen2=Screen.objects.create(theater=second,name="2")
        self.show=Show.objects.create(movie=self.movie,screen=screen,show_time=timezone.now()+timedelta(days=1),ticket_price=100)
        Show.objects.create(movie=self.movie,screen=screen2,show_time=timezone.now()+timedelta(days=2),ticket_price=500)
        self.user=User.objects.create_user("viewer")

    def test_same_show_city_theater_and_price(self):
        response=self.client.get("/movies/",{"city":"Salem","theater":self.theater.pk,"sort":"price"})
        self.assertEqual(response.context["matching_count"],1)
        self.assertEqual(response.context["page_obj"][0].minimum_price,500)
        self.assertEqual(self.client.get("/movies/",{"city":"Vellore","theater":self.theater.pk}).context["matching_count"],0)

    def test_invalid_filters_and_partial_count(self):
        self.assertEqual(self.client.get("/movies/",{"genre":"invalid"}).context["matching_count"],0)
        response=self.client.get("/movies/",{"search":"Space & Time","partial":"1"})
        self.assertContains(response,"1 matching movie")
        self.assertNotContains(response,"<html")

    def test_rating_not_multiplied_by_show_joins(self):
        Review.objects.create(movie=self.movie,user=self.user,rating=4,comment="Good")
        response=self.client.get("/movies/",{"min_rating":"4","sort":"rating"})
        self.assertEqual(response.context["matching_count"],1)
        self.assertEqual(response.context["page_obj"][0].calculated_rating,4)

    def test_recent_view_and_booking_recommendations(self):
        self.client.force_login(self.user)
        Booking.objects.create(user=self.user,show=self.show,status="CONFIRMED")
        self.client.get(f"/movies/{self.movie.pk}/")
        response=self.client.get("/movies/")
        self.assertTrue(response.context["personalized"])
        self.assertEqual(list(response.context["recommended"].values_list("pk",flat=True)),[self.other.pk])
        self.assertEqual(self.client.session["recent_movies"],[self.movie.pk])

class EntertainmentTests(TestCase):
    def test_each_navigation_destination_opens(self):
        for category in ('stream', 'events', 'plays', 'sports', 'activities'):
            response = self.client.get(f'/explore/{category}/')
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, f'/explore/{category}/')
        self.assertEqual(self.client.get('/explore/unknown/').status_code, 404)

    def test_catalog_filters_and_drafts(self):
        from .models import Experience
        from datetime import timedelta
        from django.utils import timezone
        item = Experience.objects.create(category='events', title='Evening Concert', city='Salem', venue='Hall', description='Live music', starts_at=timezone.now()+timedelta(days=3), published=True)
        draft = Experience.objects.create(category='events', title='Draft event', city='Salem', venue='Hall', description='Draft', starts_at=timezone.now()+timedelta(days=3))
        response = self.client.get('/explore/events/?q=concert&city=Salem')
        self.assertContains(response, 'Evening Concert')
        self.assertNotContains(response, 'Draft event')
        self.assertNotContains(self.client.get('/explore/plays/'), 'Evening Concert')
        self.assertNotContains(self.client.get('/explore/events/?city=Chennai'), 'Evening Concert')
        self.assertEqual(self.client.get(f'/experiences/{draft.pk}/').status_code, 404)
        self.assertContains(self.client.get(f'/experiences/{item.pk}/'), 'Bookings are not open yet.')
        item.starts_at = timezone.now()-timedelta(days=1)
        item.save()
        self.assertNotContains(self.client.get('/explore/events/'), 'Evening Concert')
        self.assertContains(self.client.get(f'/experiences/{item.pk}/'), 'This experience has ended.')

class CityNavigationTests(TestCase):
    def test_city_selection_persists_and_rejects_external_redirect(self):
        response = self.client.post('/location/', {'city':'Chennai','next':'https://example.com/'})
        self.assertRedirects(response, '/movies/?city=Chennai')
        self.assertEqual(self.client.session['selected_city'], 'Chennai')
        self.assertContains(self.client.get('/explore/events/'), 'Chennai')
        self.client.post('/location/', {'city':''})
        self.assertEqual(self.client.session['selected_city'], '')

    def test_city_validation_and_get_are_safe(self):
        self.assertEqual(self.client.get('/location/').status_code, 405)
        self.assertEqual(self.client.post('/location/', {'city':'<script>'}).status_code, 400)

    def test_search_both_catalogs_and_hide_drafts(self):
        from movies.models import Movie
        from .models import Experience
        from django.utils import timezone
        from datetime import timedelta
        Movie.objects.create(title='Festival Film', duration=100, release_date=timezone.localdate())
        Experience.objects.create(title='Festival Evening', category='events', city='Salem', venue='Hall', starts_at=timezone.now()+timedelta(days=1), published=True)
        Experience.objects.create(title='Festival Draft', category='events', city='Salem', venue='Hall', starts_at=timezone.now()+timedelta(days=1), published=False)
        response=self.client.get('/search/?q=festival')
        self.assertContains(response,'Festival Film')
        self.assertContains(response,'Festival Evening')
        self.assertNotContains(response,'Festival Draft')
        self.assertEqual(self.client.get('/search/').status_code, 200)
