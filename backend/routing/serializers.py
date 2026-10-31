from rest_framework import serializers
from datetime import timezone


class RouteRequestSerializer(serializers.Serializer):
    origin = serializers.CharField(max_length=250)
    destination = serializers.CharField(max_length=250)
    departure_time = serializers.DateTimeField(default_timezone=timezone.utc)
    sampling_interval_miles=serializers.ChoiceField(
        choices=[10,25,50],
        default=25
    )
    load_weight_lb = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=0)
    


    def validate(self, attrs):
        if attrs["origin"].casefold() == attrs["destination"].casefold():
            raise serializers.ValidationError(
                "Origin and destination must be different."
            )
        return attrs


class CorridorWeatherRequestSerializer(serializers.Serializer):
    route_plan_id = serializers.RegexField(
        regex=r"^[0-9a-f]{32}$",
        max_length=32,
    )