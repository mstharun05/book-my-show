from django.urls import path
from . import views

urlpatterns = [
    path('verify/<str:token>/', views.verify_ticket, name='verify_ticket'),
    path(
        'download/<int:booking_id>/',
        views.download_ticket,
        name='download_ticket'
    ),
]
