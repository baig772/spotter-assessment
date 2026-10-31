from django.views.generic import detail
from django.db.models.expressions import result
from logging import raiseExceptions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from .serializers import RouteRequestSerializer
from .services.mapbox import get_route_options, MapboxError
from .services.checkpoints import build_checkpoints
from .services.weather import attach_checkpoint_weather
from .services.risk import attach_checkpoint_risks
from .services.recommendations import analyze_and_recommend
from uuid import uuid4
from django.core.cache import cache
from .serializers import CorridorWeatherRequestSerializer
from .services.corridor import build_corridor_forecast
from datetime import datetime, timezone

@api_view(["GET"])
@permission_classes([AllowAny])
def health_check(request):
    return Response({
        "status": "ok",
        "service": "spotter-api",
    })


@api_view(["POST"])
@permission_classes([AllowAny])
def route_options(request):
    serializer = RouteRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    input = serializer.validated_data

    try:
        result = get_route_options(
            origin=input["origin"],
            destination=input["destination"],
        )
    except MapboxError as error:
        return Response(
            {"detail": str(error)},
            status=error.status_code,
        )

    try:
        for route in result["routes"]:
            route["checkpoints"] = build_checkpoints(
                route=route,
                departure_time=input["departure_time"],
                interval_miles=input["sampling_interval_miles"],
            )
    except ValueError as error:
        return Response(
            {"detail": str(error)},
            status=400,
        )
    

    attach_checkpoint_weather(result["routes"])
    
    attach_checkpoint_risks(result['routes'], input['load_weight_lb'])

    result["recommendation"] = analyze_and_recommend(result["routes"])

    result['load_weight_lb'] = str(input['load_weight_lb'])

    if any(not route["weather_complete"] for route in result["routes"]):
        result["warnings"].append(
            "Some checkpoints have unavailable weather. "
            "These routes cannot be fully assessed."
        )

    result['departure_time'] = (
        input["departure_time"].isoformat().replace("+00:00", "Z")
    )
    result['interval_miles'] = input['sampling_interval_miles']

    plan_id = uuid4().hex
    cache.set(
        f"route-plan:{plan_id}",
        {
            "routes": result["routes"],
            "load_weight_lb": str(input["load_weight_lb"]),
        },
        timeout=3600,
    )

    result["route_plan_id"] = plan_id

    return Response(result)


@api_view(["POST"])
@permission_classes([AllowAny])
def corridor_weather(request):
    serializer = CorridorWeatherRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    plan_id = serializer.validated_data["route_plan_id"]
    plan = cache.get(f"route-plan:{plan_id}")

    if plan is None:
        return Response(
            {"detail": "Trip plan expired. Please plan the trip again."},
            status=410,
        )

    hour_key = datetime.now(timezone.utc).strftime("%Y%m%d%H")
    response_key = f"corridor-weather:{plan_id}:{hour_key}"
    cached_result = cache.get(response_key)

    if cached_result is not None:
        return Response(cached_result)

    try:
        result = build_corridor_forecast(plan)
    except ValueError as error:
        return Response({"detail": str(error)}, status=422)

    # Do not cache partial failures as complete corridor responses.
    if not result["warnings"]:
        cache.set(response_key, result, timeout=600)

    return Response(result)

    