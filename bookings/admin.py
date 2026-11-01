
from django.contrib import admin
from .models import Theater, Screen, Seat, Show, Booking, ShowSeat

admin.site.register(Theater)
admin.site.register(Screen)
admin.site.register(Seat)
admin.site.register(Show)
admin.site.register(Booking)
admin.site.register(ShowSeat)
