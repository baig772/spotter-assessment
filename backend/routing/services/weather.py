import json
import math
from datetime import datetime, timedelta, timezone
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import urlopen

from django.core.cache import cache


FIELDS = ("wind_speed_10m", "rain", "showers", "snowfall")
CACHE_SECONDS = 600
BATCH_SIZE = 20


def unknown(reason):
    return {
        "status": "unknown",
        "reason": reason,
        "wind_mph": None,
        "rain_inches_per_hour": None,
        "snow_inches_per_hour": None,
    }


def utc_datetime(value):
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))

    # Open-Meteo returns offset-free timestamps when timezone=GMT.
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    return parsed.astimezone(timezone.utc)


def iso_utc(value):
    return value.isoformat().replace("+00:00", "Z")


def weather_at_arrival(forecast, arrival_time):
    if forecast is None:
        return unknown("Weather provider unavailable.")

    try:
        units = forecast["hourly_units"]

        if (
            units["wind_speed_10m"] not in ("mp/h", "mph")
            or units["rain"] != "mm"
            or units["showers"] != "mm"
            or units["snowfall"] != "cm"
        ):
            return unknown("Unexpected weather units.")

        hourly = forecast["hourly"]
        times = [utc_datetime(value) for value in hourly["time"]]

        if not times or any(
            len(hourly[field]) != len(times) for field in FIELDS
        ):
            return unknown("Incomplete forecast data.")

        arrival = utc_datetime(arrival_time)

        if not times[0] <= arrival <= times[-1]:
            return unknown("Arrival is outside the available forecast.")

        lower = arrival.replace(minute=0, second=0, microsecond=0)
        upper = lower if arrival == lower else lower + timedelta(hours=1)

        indices = {value: index for index, value in enumerate(times)}
        lower_index = indices[lower]
        upper_index = indices[upper]

        wind_before = hourly["wind_speed_10m"][lower_index]
        wind_after = hourly["wind_speed_10m"][upper_index]
        rain = hourly["rain"][upper_index]
        showers = hourly["showers"][upper_index]
        snow = hourly["snowfall"][upper_index]

        values = [wind_before, wind_after, rain, showers, snow]

        if any(
            value is None or not math.isfinite(value) or value < 0
            for value in values
        ):
            return unknown("Required weather readings are missing or invalid.")

        fraction = (arrival - lower).total_seconds() / 3600
        wind = wind_before + fraction * (wind_after - wind_before)

        return {
            "status": "available",
            "source": "open-meteo",
            "wind_mph": wind,
            "rain_inches_per_hour": (rain + showers) / 25.4,
            "snow_inches_per_hour": snow / 2.54,
            "precipitation_interval_start": iso_utc(
                upper - timedelta(hours=1)
            ),
            "precipitation_interval_end": iso_utc(upper),
            "wind_sample_start": iso_utc(lower),
            "wind_sample_end": iso_utc(upper),
        }

    except (KeyError, IndexError, TypeError, ValueError, AttributeError):
        return unknown("Incomplete or invalid forecast data.")


def location_key(checkpoint):
    # Approximately metre-level precision; deduplicates shared locations.
    longitude, latitude = checkpoint["coordinates"]
    return round(latitude, 5), round(longitude, 5)


def cache_key(location):
    latitude, longitude = location
    return f"weather:v1:{latitude:.5f}:{longitude:.5f}"


def fetch_forecasts(locations):
    locations = list(dict.fromkeys(locations))
    forecasts = {}
    missing = []

    for location in locations:
        cached = cache.get(cache_key(location))

        if cached is None:
            missing.append(location)
        else:
            forecasts[location] = cached

    for start in range(0, len(missing), BATCH_SIZE):
        batch = missing[start:start + BATCH_SIZE]

        params = {
            "latitude": ",".join(str(point[0]) for point in batch),
            "longitude": ",".join(str(point[1]) for point in batch),
            "hourly": ",".join(FIELDS),
            "wind_speed_unit": "mph",
            "precipitation_unit": "mm",
            "timezone": "GMT",
            "forecast_days": 7,
        }

        url = "https://api.open-meteo.com/v1/forecast?" + urlencode(params)

        try:
            with urlopen(url, timeout=20) as response:
                payload = json.load(response)

            results = payload if isinstance(payload, list) else [payload]

            if len(results) != len(batch):
                raise ValueError("Unexpected number of forecast locations.")

            for location, forecast in zip(batch, results):
                if (
                    not isinstance(forecast, dict)
                    or "hourly" not in forecast
                    or "hourly_units" not in forecast
                ):
                    forecasts[location] = None
                    continue

                forecasts[location] = forecast
                cache.set(cache_key(location), forecast, CACHE_SECONDS)

        except (URLError, TimeoutError, ValueError, UnicodeDecodeError):
            for location in batch:
                forecasts[location] = None

    return forecasts


def attach_checkpoint_weather(routes):
    checkpoints = [
        checkpoint
        for route in routes
        for checkpoint in route["checkpoints"]
    ]

    forecasts = fetch_forecasts(
        location_key(checkpoint) for checkpoint in checkpoints
    )

    for route in routes:
        missing_count = 0

        for checkpoint in route["checkpoints"]:
            checkpoint["weather"] = weather_at_arrival(
                forecasts.get(location_key(checkpoint)),
                checkpoint["arrival_time"],
            )

            if checkpoint["weather"]["status"] != "available":
                missing_count += 1

        route["weather_complete"] = missing_count == 0
        route["unknown_weather_checkpoints"] = missing_count