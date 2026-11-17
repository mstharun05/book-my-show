import os
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import BaseCommand, call_command
from django.db import transaction
from movies.models import Movie


class Command(BaseCommand):
    help = 'Import the existing public catalog once and optionally create an admin from environment variables.'

    @transaction.atomic
    def handle(self, *args, **options):
        fixture = settings.BASE_DIR / 'discovery' / 'fixtures' / 'public_catalog.json'
        if fixture.exists() and not Movie.objects.exists():
            call_command('loaddata', str(fixture), verbosity=0)
            self.stdout.write('Public catalog imported.')
        username = os.environ.get('DJANGO_SUPERUSER_USERNAME')
        password = os.environ.get('DJANGO_SUPERUSER_PASSWORD')
        if username and password:
            user_model = get_user_model()
            if not user_model.objects.filter(username=username).exists():
                user_model.objects.create_superuser(username=username, email=os.environ.get('DJANGO_SUPERUSER_EMAIL', ''), password=password)
                self.stdout.write('Deployment admin created.')
