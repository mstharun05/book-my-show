
from django.contrib import admin
from .models import Payment, PaymentAttempt

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'booking',
        'amount',
        'status',
        'created_at'
    )
    list_filter = ('status',)
    search_fields = ('razorpay_order_id', 'razorpay_payment_id')


@admin.register(PaymentAttempt)
class PaymentAttemptAdmin(admin.ModelAdmin):
    list_display = ("transaction_id", "payment", "amount", "status", "updated_at")
    list_filter = ("status",)
    search_fields = ("transaction_id", "payment__razorpay_order_id")
    readonly_fields = ("payment", "transaction_id", "status", "amount", "error", "created_at", "updated_at")

    def has_add_permission(self, request):
        return False
