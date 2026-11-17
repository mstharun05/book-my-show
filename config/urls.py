
from django.contrib import admin
from django.contrib.auth import views as auth_views

from .account_views import signup, account_email
from discovery.catalog import category, experience_detail
from .health import health
from django.urls import path, include
from django.views.generic import RedirectView

urlpatterns = [
    path('health/', health, name='health'),
    path('explore/<str:category>/', category, name='entertainment_category'),
    path('experiences/<int:pk>/', experience_detail, name='experience_detail'),
    path('accounts/email/', account_email, name='account_email'),
    path('', RedirectView.as_view(url='/movies/', permanent=False)),
    path("accounts/login/", auth_views.LoginView.as_view(), name="login"),
    path("accounts/logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("accounts/signup/", signup, name="signup"),
    path('admin/', admin.site.urls),
    path('dashboard/', include('dashboard.urls')),
    path('movies/', include('discovery.urls')),
    path('tickets/', include('tickets.urls')),
    path('bookings/', include('bookings.urls')),
    path('payments/', include('payments.urls')),
    path("movie-details/", include("movies.urls")),
]
