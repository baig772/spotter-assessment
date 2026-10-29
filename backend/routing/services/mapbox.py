import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

from django.conf import settings


class MapboxError(Exception):
    def __init__(self, message, status_code=502):
        super().__init__(message)
        self.status_code = status_code


def _get_json(path, params):
    token = settings.MAPBOX_ACCESS_TOKEN

    if not token:
        raise MapboxError("Routing service is not configured.", 503)

    query = urlencode({**params, "access_token": token})
    url = f"https://api.mapbox.com/{path}?{query}"

    try:
        with urlopen(url, timeout=15) as response:
            return json.load(response)
    except HTTPError as error:
        if error.code == 429:
            raise MapboxError(
                "Routing provider is busy. Please try again shortly.", 503
            ) from None

        raise MapboxError("Routing provider rejected the request.") from None
    except (TimeoutError, URLError):
        raise MapboxError(
            "Routing provider could not be reached. Please try again.", 503
        ) from None
    except (ValueError, UnicodeDecodeError):
        raise MapboxError("Routing provider returned an invalid response.") from None


def geocode(query):
    data = _get_json(
        "search/geocode/v6/forward",
        {
            "q": query,
            "limit": 1,
            "autocomplete": "false",
        },
    )

    features = data.get("features", [])

    if not features:
        raise MapboxError(f"No location found for '{query}'.", 422)

    feature = features[0]
    coordinates = feature["geometry"]["coordinates"]
    properties = feature.get("properties", {})

    return {
        "name": properties.get("full_address")
        or properties.get("name")
        or query,
        "coordinates": coordinates,
    }


def get_route_options(origin_query, destination_query):
    origin = geocode(origin_query)
    destination = geocode(destination_query)

    if origin["coordinates"] == destination["coordinates"]:
        raise MapboxError(
            "Origin and destination resolve to the same location.", 422
        )

    coordinates = ";".join(
        ",".join(str(value) for value in location["coordinates"])
        for location in (origin, destination)
    )

    data = _get_json(
        f"directions/v5/mapbox/driving/{coordinates}",
        {
            "alternatives": "true",
            "geometries": "geojson",
            "overview": "full",
            "annotations": "distance,duration",
            "steps": "false",
        },
    )

    code = data.get("code")

    if code in {"NoRoute", "NoSegment"}:
        raise MapboxError(
            "No driving route was found between these locations.", 422
        )

    if code != "Ok":
        raise MapboxError("Routing provider could not calculate routes.")

    routes = []
    seen_geometries = set()

    for route in data.get("routes", []):
        geometry = route["geometry"]
        geometry_key = json.dumps(geometry["coordinates"])

        if geometry_key in seen_geometries:
            continue

        seen_geometries.add(geometry_key)

        distances = []
        durations = []

        for leg in route.get("legs", []):
            annotation = leg.get("annotation", {})
            distances.extend(annotation.get("distance", []))
            durations.extend(annotation.get("duration", []))

        expected_segments = len(geometry["coordinates"]) - 1

        if (
            expected_segments < 1
            or len(distances) != expected_segments
            or len(durations) != expected_segments
            or any(value is None or value < 0 for value in distances)
            or any(value is None or value < 0 for value in durations)
        ):
            raise MapboxError(
                "Routing provider returned incomplete segment timing."
            )

        routes.append({
            "id": f"route-{len(routes) + 1}",
            "distance_meters": route["distance"],
            "duration_seconds": route["duration"],
            "geometry": geometry,
            "segments": {
                "distances_meters": distances,
                "durations_seconds": durations,
            },
        })

        if len(routes) == 3:
            break

    if not routes:
        raise MapboxError(
            "No driving route was found between these locations.", 422
        )

    warnings = []

    if len(routes) < 3:
        warnings.append(
            f"The provider returned {len(routes)} distinct routes; "
            "three alternatives are not available for this request."
        )

    return {
        "origin": origin,
        "destination": destination,
        "routes": routes,
        "warnings": warnings,
    }