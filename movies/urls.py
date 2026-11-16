
from django.urls import path
from . import views

app_name = "movies"

urlpatterns = [
    path("<int:movie_id>/", views.movie_detail, name="movie_detail"),
    path("<int:movie_id>/review/", views.submit_review, name="submit_review"),
    path("reviews/<int:review_id>/report/", views.report_review, name="report_review"),
]
