from django.contrib import admin
from .models import Experience


@admin.register(Experience)
class ExperienceAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'city', 'venue', 'starts_at', 'price', 'published')
    list_filter = ('category', 'published', 'city')
    search_fields = ('title', 'venue', 'city')
    date_hierarchy = 'starts_at'

# Register your models here.
