from django.db import migrations


def backfill(apps, schema_editor):
    Booking = apps.get_model("bookings", "Booking")
    ShowSeat = apps.get_model("bookings", "ShowSeat")
    Payment = apps.get_model("payments", "Payment")
    Attempt = apps.get_model("payments", "PaymentAttempt")
    alias = schema_editor.connection.alias
    for booking in Booking.objects.using(alias).all().iterator():
        numbers = list(ShowSeat.objects.using(alias).filter(booking_id=booking.pk).values_list("seat__seat_number", flat=True))
        Booking.objects.using(alias).filter(pk=booking.pk).update(seat_numbers=numbers)
    for payment in Payment.objects.using(alias).exclude(razorpay_payment_id=None).exclude(razorpay_payment_id="").iterator():
        status = {"SUCCESS": "captured", "FAILED": "failed", "REFUNDED": "refunded"}.get(payment.status, "created")
        Attempt.objects.using(alias).get_or_create(
            transaction_id=payment.razorpay_payment_id,
            defaults={"payment_id":payment.pk, "amount":payment.amount, "status":status}
        )


class Migration(migrations.Migration):
    dependencies = [("payments", "0002_alter_payment_status_paymentattempt"), ("bookings", "0003_booking_seat_numbers")]
    operations = [migrations.RunPython(backfill, migrations.RunPython.noop)]
