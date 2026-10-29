from unicodedata import name
from django.urls import path

from .views import health_check, route_options

urlpatterns = [
    path("health/", health_check, name="health"),
    path("routes/", route_options, name="route-options")
]