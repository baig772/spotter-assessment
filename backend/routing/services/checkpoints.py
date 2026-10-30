from bisect import bisect_right
from datetime import timedelta, timezone
from itertools import accumulate
from math import isfinite


METERS_PER_MILE = 1609.344
INTERVAL_MILES = [10,25,50]

def build_checkpoints(route, departure_time, interval_miles):
    if interval_miles not in INTERVAL_MILES:
        raise ValueError("Sampling interval must be 10, 25, or 50 miles.")

    if departure_time.utcoffset() is None:
        raise ValueError("Departure time must include a timezone.")

    coordinates = route["geometry"]["coordinates"]
    distances = route["segments"]["distances_meters"]
    durations = route["segments"]["durations_seconds"]

    if (
        len(coordinates) < 2
        or len(distances) != len(coordinates) - 1
        or len(durations) != len(distances)
    ):
        raise ValueError("Route geometry and segment data do not align.")

    if any(
        not isfinite(value) or value < 0
        for value in [*distances, *durations]
    ):
        raise ValueError("Segment distances and durations must be valid.")

    cumulative_distances = list(accumulate(distances, initial=0.0))
    cumulative_durations = list(accumulate(durations, initial=0.0))

    total_distance = cumulative_distances[-1]
    total_duration = cumulative_durations[-1]

    if total_distance <= 0:
        raise ValueError("Route distance must be positive.")

    interval_meters = interval_miles * METERS_PER_MILE

    # Keep the endpoint separate to avoid duplicate destination checkpoints.
    targets = [0.0]
    next_distance = interval_meters

    while next_distance < total_distance - 0.001:
        targets.append(next_distance)
        next_distance += interval_meters

    targets.append(total_distance)

    departure_utc = departure_time.astimezone(timezone.utc)
    checkpoints = []

    for index, target in enumerate(targets):
        if index == 0:
            longitude, latitude = coordinates[0]
            elapsed_seconds = 0.0

        elif index == len(targets) - 1:
            longitude, latitude = coordinates[-1]
            elapsed_seconds = total_duration

        else:
            segment_index = (
                bisect_right(cumulative_distances, target) - 1
            )

            segment_distance = distances[segment_index]
            fraction = (
                target - cumulative_distances[segment_index]
            ) / segment_distance

            start_lon, start_lat = coordinates[segment_index]
            end_lon, end_lat = coordinates[segment_index + 1]

            # Follow the short longitude direction across the antimeridian.
            longitude_delta = (end_lon - start_lon + 180) % 360 - 180
            longitude = (
                start_lon + fraction * longitude_delta + 180
            ) % 360 - 180

            latitude = start_lat + fraction * (end_lat - start_lat)

            elapsed_seconds = (
                cumulative_durations[segment_index]
                + fraction * durations[segment_index]
            )

        arrival_time = departure_utc + timedelta(
            seconds=elapsed_seconds
        )

        checkpoints.append({
            "id": f"{route['id']}-checkpoint-{index}",
            "coordinates": [longitude, latitude],
            "distance_from_start_meters": target,
            "elapsed_seconds": elapsed_seconds,
            "arrival_time": arrival_time.isoformat().replace("+00:00", "Z"),
        })

    return checkpoints