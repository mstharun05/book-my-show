
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Sum, Count
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone
import csv

from bookings.models import Booking
from payments.models import Payment


@staff_member_required
def dashboard_home(request):
    today = timezone.localdate()

    total_bookings = Booking.objects.filter(
        status='CONFIRMED'
    ).count()

    total_revenue = Payment.objects.filter(
        status='SUCCESS'
    ).aggregate(total=Sum('amount'))['total'] or 0

    today_revenue = Payment.objects.filter(
        status='SUCCESS',
        created_at__date=today
    ).aggregate(total=Sum('amount'))['total'] or 0

    monthly_revenue = Payment.objects.filter(
        status='SUCCESS',
        created_at__year=today.year,
        created_at__month=today.month
    ).aggregate(total=Sum('amount'))['total'] or 0

    popular_movies = (
        Booking.objects.filter(status='CONFIRMED')
        .values('show__movie__title')
        .annotate(total=Count('id'))
        .order_by('-total')[:5]
    )

    context = {
        'total_bookings': total_bookings,
        'total_revenue': total_revenue,
        'today_revenue': today_revenue,
        'monthly_revenue': monthly_revenue,
        'popular_movies': popular_movies,
    }

    return render(request, 'dashboard/home.html', context)


@staff_member_required
def export_csv(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = (
        'attachment; filename="booking_report.csv"'
    )

    writer = csv.writer(response)
    writer.writerow(['Booking ID', 'Movie', 'User', 'Status'])

    bookings = Booking.objects.select_related(
        'show__movie', 'user'
    ).all()

    for booking in bookings:
        writer.writerow([
            booking.id,
            booking.show.movie.title,
            booking.user.username,
            booking.status,
        ])

    return response
