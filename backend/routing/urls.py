from django.urls import path

from .views import corridor_weather, health_check, route_options

urlpatterns = [
    path("health/", health_check, name="health"),
    path("routes/", route_options, name="route-options"),
    path(
        "corridor-weather/",
        corridor_weather,
        name="corridor-weather",
    ),
]