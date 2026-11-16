from django.urls import path
from . import views

app_name = "bookings"

urlpatterns = [
    path(
        "show/<int:show_id>/",
        views.seat_selection_page,
        name="seat_selection"
    ),

    path(
        "show/<int:show_id>/seats/",
        views.seat_availability,
        name="seat_availability"
    ),

    path(
        "show/<int:show_id>/reserve/",
        views.reserve_selected_seats,
        name="reserve_seats"
    ),
]