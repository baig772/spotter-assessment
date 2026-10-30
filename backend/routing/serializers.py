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


    def validate(self, attrs):
        if attrs["origin"].casefold() == attrs["destination"].casefold():
            raise serializers.ValidationError(
                "Origin and destination must be different."
            )
        return attrs