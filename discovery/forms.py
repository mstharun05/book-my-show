from django import forms
from movies.models import Genre, Language
from bookings.models import Theater


class DiscoveryForm(forms.Form):
    search = forms.CharField(required=False, max_length=200, label="Movie title")
    genre = forms.ModelChoiceField(Genre.objects.order_by("name"), required=False, empty_label="All genres")
    language = forms.ModelChoiceField(Language.objects.order_by("name"), required=False, empty_label="All languages")
    city = forms.CharField(required=False, max_length=100)
    theater = forms.ModelChoiceField(Theater.objects.order_by("name"), required=False, empty_label="All theaters")
    release_from = forms.DateField(required=False, widget=forms.DateInput(attrs={"type":"date"}))
    release_to = forms.DateField(required=False, widget=forms.DateInput(attrs={"type":"date"}))
    min_rating = forms.DecimalField(required=False, min_value=0, max_value=5, decimal_places=1, label="Minimum rating")
    show_from = forms.DateTimeField(required=False, widget=forms.DateTimeInput(attrs={"type":"datetime-local"}), label="Shows from (IST)")
    show_to = forms.DateTimeField(required=False, widget=forms.DateTimeInput(attrs={"type":"datetime-local"}), label="Shows through (IST)")
    sort = forms.ChoiceField(required=False, choices=[
        ("newest","Newest releases"), ("popular","Most popular"),
        ("rating","Highest rated"), ("price","Lowest ticket price"), ("price_desc","Highest ticket price"),
    ])

    def clean(self):
        data = super().clean()
        for start, end in (("release_from","release_to"), ("show_from","show_to")):
            if data.get(start) and data.get(end) and data[start] > data[end]:
                self.add_error(end, "End must be on or after start.")
        return data
