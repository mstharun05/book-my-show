
from django.urls import path
from . import views
from movies.views import movie_detail

app_name = "discovery"

urlpatterns = [
    path("", views.movie_list, name="movie_list"),
    path("<int:movie_id>/", movie_detail, name="movie_detail"),
]
