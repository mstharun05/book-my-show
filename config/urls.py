from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView

urlpatterns = [
    path('', RedirectView.as_view(url='/movies/', permanent=False)),
    path('admin/', admin.site.urls),
    path('dashboard/', include('dashboard.urls')),
    path('movies/', include('discovery.urls')),
    path('tickets/', include('tickets.urls')),
]