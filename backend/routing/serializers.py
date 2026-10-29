from rest_framework import serializers

class RouteRequestSerializer(serializers.Serializer):
    origin = serializers.CharField(max_length=250)
    destination = serializers.CharField(max_length=250)

    def validate(self, attrs):
        if attrs["origin"].casefold() == attrs["destination"].casefold():
            raise serializers.ValidationError(
                "Origin and destination must be different."
            )
        return attrs