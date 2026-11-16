
from django.contrib import admin
from .models import (
    Movie,
    Genre,
    Language,
    CastMember,
    PosterImage,
    Review,
)


class PosterImageInline(admin.TabularInline):
    model = PosterImage
    extra = 1


@admin.register(Movie)
class MovieAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "release_date",
        "age_certificate",
        "duration",
        "display_rating",
    )

    search_fields = ("title", "description")
    list_filter = ("age_certificate", "release_date")
    filter_horizontal = ("genre", "languages", "cast")
    inlines = [PosterImageInline]

    @admin.display(description="Average Rating")
    def display_rating(self, obj):
        return obj.average_rating


@admin.register(Genre)
class GenreAdmin(admin.ModelAdmin):
    search_fields = ("name",)


@admin.register(Language)
class LanguageAdmin(admin.ModelAdmin):
    search_fields = ("name",)


@admin.register(CastMember)
class CastMemberAdmin(admin.ModelAdmin):
    search_fields = ("name",)


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = (
        "movie",
        "user",
        "rating",
        "verified_viewer",
        "reported",
        "created_at",
    )

    list_filter = (
        "rating",
        "verified_viewer",
        "reported",
    )

    search_fields = (
        "movie__title",
        "user__username",
    )

    readonly_fields = (
        "verified_viewer",
        "created_at",
        "updated_at",
    )

    actions = ["clear_reports"]

    @admin.action(description="Mark selected reviews as reviewed")
    def clear_reports(self, request, queryset):
        queryset.update(reported=False)
