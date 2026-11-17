from django.contrib import admin
from django.utils import timezone

from movies.services import completed_bookings

from .models import Booking, Screen, Seat, Show, ShowSeat, Theater


@admin.register(Theater)
class TheaterAdmin(admin.ModelAdmin):
    list_display = ("name", "city")
    search_fields = ("name", "city")


@admin.register(Show)
class ShowAdmin(admin.ModelAdmin):
    list_display = ("movie", "screen", "show_time", "ticket_price")
    list_filter = ("show_time", "screen__theater")
    search_fields = ("movie__title", "screen__theater__name")
    autocomplete_fields = ("movie",)


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "show", "status", "attended_at")
    list_filter = ("status", "attended_at")
    search_fields = ("=id", "user__username", "show__movie__title")
    readonly_fields = ("attended_at",)
    actions = ("verify_attendance",)

    @admin.action(description="Confirm attendance for completed bookings", permissions=["change"])
    def verify_attendance(self, request, queryset):
        pending = queryset.filter(attended_at__isnull=True)
        count = pending.filter(pk__in=completed_bookings(pending)).update(
            attended_at=timezone.now()
        )
        self.message_user(request, f"Attendance confirmed for {count} booking(s).")


admin.site.register(Screen)
admin.site.register(Seat)
admin.site.register(ShowSeat)
