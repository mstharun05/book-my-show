from django.db import migrations


def reset_legacy_badges(apps, schema_editor):
    review = apps.get_model("movies", "Review")
    review.objects.using(schema_editor.connection.alias).filter(
        verified_viewer=True
    ).update(verified_viewer=False)


class Migration(migrations.Migration):
    dependencies = [
        ("movies", "0002_review_updated_at"),
        ("bookings", "0002_booking_attended_at"),
    ]

    operations = [
        migrations.RunPython(reset_legacy_badges, migrations.RunPython.noop),
    ]
