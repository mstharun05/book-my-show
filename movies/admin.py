
from django.contrib import admin
from .models import Genre, Language, CastMember, Movie, PosterImage, Review


class PosterImageInline(admin.TabularInline):
    model = PosterImage
    extra = 1


@admin.register(Movie)
class MovieAdmin(admin.ModelAdmin):
    list_display = ('title', 'age_certificate', 'duration', 'release_date')
    search_fields = ('title',)
    list_filter = ('age_certificate', 'release_date')
    filter_horizontal = ('genre', 'languages', 'cast')
    inlines = [PosterImageInline]


admin.site.register(Genre)
admin.site.register(Language)
admin.site.register(CastMember)
admin.site.register(Review)
