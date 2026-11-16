
import os
from django.contrib.auth import get_user_model

def create_admin():
    username = os.environ.get("ADMIN_USERNAME")
    password = os.environ.get("ADMIN_PASSWORD")

    if not username or not password:
        return

    User = get_user_model()
    user, _ = User.objects.get_or_create(username=username)
    user.is_staff = True
    user.is_superuser = True
    user.is_active = True
    user.set_password(password)
    user.save()

