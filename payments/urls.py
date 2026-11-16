
from django.urls import path
from . import views

app_name = "payments"

urlpatterns = [
    path("create/<int:booking_id>/", views.create_payment_order, name="create_payment_order"),
    path("verify/", views.verify_payment, name="verify_payment"),
    path("confirmation/<int:booking_id>/", views.booking_confirmation, name="booking_confirmation"),
]
