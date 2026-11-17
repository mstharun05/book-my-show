from django.contrib import admin

from .models import TicketDelivery


@admin.register(TicketDelivery)
class TicketDeliveryAdmin(admin.ModelAdmin):
    list_display = ('booking_id', 'attempts', 'sent_at', 'next_attempt_at', 'last_error')
    exclude = ('pdf',)
    readonly_fields = ('booking', 'attempts', 'sent_at', 'next_attempt_at', 'last_error')

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
