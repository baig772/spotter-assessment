from django.views.generic import detail
from django.db.models.expressions import result
from logging import raiseExceptions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from .serializers import RouteRequestSerializer
from .services.mapbox import get_route_options, MapboxError


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

    try:
        result = get_route_options(
            origin_query=serializer.validated_data["origin"],
            destination_query=serializer.validated_data["destination"],
        )
    except MapboxError as error:
        return Response(
            {"detail": str(error)},
            status=error.status_code,
        )
    return Response(result)

    