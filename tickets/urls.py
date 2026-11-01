from django.urls import path
from . import views

urlpatterns = [
    path(
        'download/<int:booking_id>/',
        views.download_ticket,
        name='download_ticket'
    ),
]