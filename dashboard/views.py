import csv

from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import permission_required
from django.http import JsonResponse, StreamingHttpResponse
from django.shortcuts import render
from django.utils import timezone

from bookings.models import Booking
from .analytics import DateRangeForm, analytics, midnight
from datetime import timedelta


def dashboard_access(view):
    return staff_member_required(permission_required(
        "dashboard.view_business_dashboard", raise_exception=True
    )(view))


def report_context(request):
    form = DateRangeForm(request.GET)
    if not form.is_valid():
        return form, None
    start, end = form.cleaned_data["start"], form.cleaned_data["end"]
    return form, {"start": start, "end": end, "generated": timezone.now(), **analytics(start, end)}


@dashboard_access
def dashboard_home(request):
    form = DateRangeForm(request.GET)
    valid = form.is_valid()
    return render(request, "dashboard/home.html", {"form": form}, status=200 if valid else 400)


@dashboard_access
def live_data(request):
    form, context = report_context(request)
    if context is None:
        return JsonResponse({"errors": form.errors}, status=400)
    return JsonResponse(context)


class CSVBuffer:
    def write(self, value):
        return value


def safe_cell(value):
    text = str(value if value is not None else "")
    return "'" + text if text.lstrip().startswith(("=", "+", "-", "@")) else text


@dashboard_access
def export_csv(request):
    form = DateRangeForm(request.GET)
    if not form.is_valid():
        return JsonResponse({"errors": form.errors}, status=400)
    start, end = form.cleaned_data["start"], form.cleaned_data["end"]
    writer = csv.writer(CSVBuffer())
    if request.GET.get("type") == "bookings":
        rows = Booking.objects.filter(
            created_at__gte=midnight(start), created_at__lt=midnight(end+timedelta(days=1))
        ).order_by("id").values_list(
            "id", "show__movie__title", "show__screen__theater__name",
            "user__username", "status", "created_at"
        )
        def stream():
            yield writer.writerow(["Booking ID", "Movie", "Theater", "User", "Status", "Created"])
            for row in rows.iterator(chunk_size=2000):
                yield writer.writerow([safe_cell(value) for value in row])
    else:
        data = analytics(start, end)
        def stream():
            yield writer.writerow(["Report range", start.isoformat(), end.isoformat()])
            for section, values in data.items():
                if isinstance(values, dict):
                    yield writer.writerow([section, "Metric", "Value"])
                    for key, value in values.items():
                        yield writer.writerow([section, key, safe_cell(value)])
                elif isinstance(values, list):
                    yield writer.writerow([section])
                    if values:
                        yield writer.writerow(list(values[0]))
                        for row in values:
                            yield writer.writerow([safe_cell(value) for value in row.values()])
                else:
                    yield writer.writerow([section, safe_cell(values)])
    response = StreamingHttpResponse(stream(), content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="business-report.csv"'
    return response
