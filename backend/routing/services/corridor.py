import math
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from .risk import assess_checkpoint_risk
from .weather import fetch_forecasts, iso_utc, weather_at_arrival


EARTH_RADIUS_METERS = 6371000
MAX_GRID_POINTS = 100
BASE_GRID_SPACING_METERS = 20000
CORRIDOR_RADIUS_METERS = 25000
ROUTE_SAMPLE_SPACING_METERS = 10000


def build_corridor_grid(routes):
    coordinates = [
        coordinate
        for route in routes
        for coordinate in route["geometry"]["coordinates"]
    ]

    if not coordinates:
        raise ValueError("Routes contain no coordinates.")

    longitudes = [point[0] for point in coordinates]
    latitudes = [point[1] for point in coordinates]

    # This lightweight local projection is intended for regional road trips.
    if (
        max(longitudes) - min(longitudes) > 60
        or max(latitudes) - min(latitudes) > 30
        or max(abs(latitude) for latitude in latitudes) > 70
    ):
        raise ValueError(
            "This trip exceeds the supported regional weather-grid area."
        )

    origin_lon = (min(longitudes) + max(longitudes)) / 2
    origin_lat = (min(latitudes) + max(latitudes)) / 2
    cos_latitude = math.cos(math.radians(origin_lat))

    def project(coordinate):
        longitude, latitude = coordinate
        return (
            EARTH_RADIUS_METERS
            * math.radians(longitude - origin_lon)
            * cos_latitude,
            EARTH_RADIUS_METERS * math.radians(latitude - origin_lat),
        )

    def unproject(x, y):
        return [
            origin_lon
            + math.degrees(x / (EARTH_RADIUS_METERS * cos_latitude)),
            origin_lat + math.degrees(y / EARTH_RADIUS_METERS),
        ]

    samples = []

    for route in routes:
        line = [project(point) for point in route["geometry"]["coordinates"]]

        if not line:
            continue

        samples.append(line[0])

        for start, end in zip(line, line[1:]):
            distance = math.hypot(end[0] - start[0], end[1] - start[1])
            steps = max(1, math.ceil(distance / ROUTE_SAMPLE_SPACING_METERS))

            for step in range(1, steps + 1):
                fraction = step / steps
                samples.append((
                    start[0] + fraction * (end[0] - start[0]),
                    start[1] + fraction * (end[1] - start[1]),
                ))

    # Deduplicate nearby geometry samples to reduce grid-generation work.
    samples = list({
        (round(x / 1000) * 1000, round(y / 1000) * 1000)
        for x, y in samples
    })

    spacing = float(BASE_GRID_SPACING_METERS)

    while True:
        # Increase coverage radius with coarse spacing to avoid empty gaps.
        radius = max(CORRIDOR_RADIUS_METERS, spacing * 0.8)
        cells = set()

        for x, y in samples:
            min_x = math.ceil((x - radius) / spacing)
            max_x = math.floor((x + radius) / spacing)
            min_y = math.ceil((y - radius) / spacing)
            max_y = math.floor((y + radius) / spacing)

            for grid_x in range(min_x, max_x + 1):
                for grid_y in range(min_y, max_y + 1):
                    if math.hypot(
                        grid_x * spacing - x,
                        grid_y * spacing - y,
                    ) <= radius:
                        cells.add((grid_x, grid_y))

        if len(cells) <= MAX_GRID_POINTS:
            break

        spacing *= 1.4

    points = [
        {
            "id": f"grid-{index}",
            "coordinates": [
                round(value, 5)
                for value in unproject(grid_x * spacing, grid_y * spacing)
            ],
        }
        for index, (grid_x, grid_y) in enumerate(sorted(cells))
    ]

    return {
        "points": points,
        "grid_spacing_meters": spacing,
        "corridor_radius_meters": radius,
    }


def build_corridor_forecast(plan, reference_time=None):
    grid = build_corridor_grid(plan["routes"])

    reference = reference_time or datetime.now(timezone.utc)
    reference = reference.astimezone(timezone.utc).replace(
        minute=0, second=0, microsecond=0
    )

    times = [
        iso_utc(reference + timedelta(hours=hour))
        for hour in range(49)
    ]

    locations = [
        (point["coordinates"][1], point["coordinates"][0])
        for point in grid["points"]
    ]

    forecasts = fetch_forecasts(locations)
    load = Decimal(plan["load_weight_lb"])
    missing_samples = 0

    for point, location in zip(grid["points"], locations):
        forecast = forecasts.get(location)
        samples = []

        for timestamp in times:
            weather = weather_at_arrival(forecast, timestamp)
            risk = assess_checkpoint_risk(weather, load)

            if weather["status"] != "available":
                missing_samples += 1

            samples.append({
                "status": weather["status"],
                "wind_mph": weather["wind_mph"],
                "rain_inches_per_hour": weather["rain_inches_per_hour"],
                "snow_inches_per_hour": weather["snow_inches_per_hour"],
                "severity": risk["severity"],
                "score": risk["score"],
            })

        point["forecasts"] = samples

    warnings = []

    if missing_samples:
        warnings.append(
            f"{missing_samples} grid-hour samples are unavailable. "
            "Missing data must not be displayed as Low risk."
        )

    return {
        "reference_time": iso_utc(reference),
        "times": times,
        "load_weight_lb": str(load),
        "grid_spacing_meters": grid["grid_spacing_meters"],
        "corridor_radius_meters": grid["corridor_radius_meters"],
        "points": grid["points"],
        "warnings": warnings,
    }