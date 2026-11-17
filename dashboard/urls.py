from django.urls import path
from . import views

urlpatterns = [
    path("", views.dashboard_home, name="dashboard_home"),
    path("data/", views.live_data, name="dashboard_data"),
    path("export/", views.export_csv, name="export_csv"),
]
