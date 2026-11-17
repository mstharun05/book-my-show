from django.db import migrations, models


def add_user_index(apps, schema_editor):
    schema_editor.add_index(apps.get_model("auth", "User"), models.Index(fields=["date_joined"], name="user_joined_analytics_idx"))


def remove_user_index(apps, schema_editor):
    schema_editor.remove_index(apps.get_model("auth", "User"), models.Index(fields=["date_joined"], name="user_joined_analytics_idx"))


class Migration(migrations.Migration):
    dependencies = [("dashboard", "0001_initial"), ("auth", "0012_alter_user_first_name_max_length")]
    operations = [migrations.RunPython(add_user_index, remove_user_index)]
