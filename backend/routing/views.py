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


    return Response(result)

    