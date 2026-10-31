from datetime import datetime, timezone

from django.test import SimpleTestCase
from django.core.cache import cache
from unittest.mock import patch
from decimal import Decimal
from .services.checkpoints import METERS_PER_MILE, build_checkpoints
from .services.weather import (fetch_forecasts, weather_at_arrival)

from .serializers import RouteRequestSerializer
from .services.risk import (
    assess_checkpoint_risk,
    classify_rain,
    classify_snow,
    classify_wind,
)



class CheckpointTests(SimpleTestCase):
    def setUp(self):
        self.departure = datetime(
            2026, 10, 30, 12, 0, tzinfo=timezone.utc
        )
        self.route = {
            "id": "route-1",
            "geometry": {
                "coordinates": [[0, 0], [1, 0], [2, 0]],
            },
            "segments": {
                "distances_meters": [
                    20 * METERS_PER_MILE,
                    20 * METERS_PER_MILE,
                ],
                "durations_seconds": [1200, 2400],
            },
        }

    def test_checkpoint_uses_segment_timing(self):
        points = build_checkpoints(self.route, self.departure, 25)

        self.assertEqual(len(points), 3)
        self.assertAlmostEqual(points[1]["coordinates"][0], 1.25)
        self.assertAlmostEqual(
            points[1]["elapsed_seconds"],
            1800,
            places=6,
        )
        self.assertEqual(
            points[1]["arrival_time"], "2026-10-30T12:30:00Z"
        )

    def test_final_partial_interval_includes_destination(self):
        points = build_checkpoints(self.route, self.departure, 25)

        self.assertEqual(points[-1]["coordinates"], [2, 0])
        self.assertAlmostEqual(
            points[-1]["distance_from_start_meters"],
            40 * METERS_PER_MILE,
        )
        self.assertEqual(
            points[-1]["arrival_time"], "2026-10-30T13:00:00Z"
        )

    def test_exact_interval_does_not_duplicate_destination(self):
        points = build_checkpoints(self.route, self.departure, 10)

        self.assertEqual(len(points), 5)
        self.assertEqual(
            sum(point["coordinates"] == [2, 0] for point in points),
            1,
        )

    def test_short_route_has_start_and_end(self):
        points = build_checkpoints(self.route, self.departure, 50)

        self.assertEqual(len(points), 2)

    def test_invalid_interval_is_rejected(self):
        with self.assertRaises(ValueError):
            build_checkpoints(self.route, self.departure, 15)


class WeatherTests(SimpleTestCase):
    def setUp(self):
        cache.clear()
        self.forecast = {
            "hourly_units": {
                "wind_speed_10m": "mp/h",
                "rain": "mm",
                "showers": "mm",
                "snowfall": "cm",
            },
            "hourly": {
                "time": [
                    "2026-10-30T12:00",
                    "2026-10-30T13:00",
                ],
                "wind_speed_10m": [10, 20],
                "rain": [0, 20.32],
                "showers": [0, 5.08],
                "snowfall": [0, 2.54],
            },
        }

    def test_arrival_uses_correct_interval_and_units(self):
        result = weather_at_arrival(
            self.forecast, "2026-10-30T12:30:00Z"
        )

        self.assertEqual(result["status"], "available")
        self.assertAlmostEqual(result["wind_mph"], 15)
        self.assertAlmostEqual(result["rain_inches_per_hour"], 1)
        self.assertAlmostEqual(result["snow_inches_per_hour"], 1)
        self.assertEqual(
            result["precipitation_interval_end"],
            "2026-10-30T13:00:00Z",
        )

    def test_exact_hour_uses_that_timestamp(self):
        result = weather_at_arrival(
            self.forecast, "2026-10-30T12:00:00Z"
        )

        self.assertEqual(result["wind_mph"], 10)
        self.assertEqual(result["rain_inches_per_hour"], 0)

    def test_timezone_offset_matches_same_instant(self):
        result = weather_at_arrival(
            self.forecast, "2026-10-30T17:30:00+05:00"
        )

        self.assertAlmostEqual(result["wind_mph"], 15)

    def test_missing_reading_is_unknown(self):
        self.forecast["hourly"]["rain"][1] = None

        result = weather_at_arrival(
            self.forecast, "2026-10-30T12:30:00Z"
        )

        self.assertEqual(result["status"], "unknown")
        self.assertIsNone(result["rain_inches_per_hour"])

    def test_out_of_range_is_unknown(self):
        result = weather_at_arrival(
            self.forecast, "2026-11-10T12:30:00Z"
        )

        self.assertEqual(result["status"], "unknown")

    @patch("routing.services.weather.urlopen")
    def test_shared_locations_and_cache_avoid_repeat_requests(self, mock_open):
        import json

        mock_open.return_value.__enter__.return_value.read.return_value = (
            json.dumps(self.forecast).encode()
        )

        location = (41.88, -87.63)

        first = fetch_forecasts([location, location])
        second = fetch_forecasts([location])

        self.assertEqual(first[location], self.forecast)
        self.assertEqual(second[location], self.forecast)
        self.assertEqual(mock_open.call_count, 1)

    @patch("routing.services.weather.urlopen")
    def test_provider_failure_returns_unavailable(self, mock_open):
        from urllib.error import URLError

        mock_open.side_effect = URLError("Unavailable")
        location = (41.88, -87.63)

        result = fetch_forecasts([location])

        self.assertIsNone(result[location])


class RiskTests(SimpleTestCase):
    def weather(self, wind=0, rain=0, snow=0):
        return {
            "status": "available",
            "wind_mph": wind,
            "rain_inches_per_hour": rain,
            "snow_inches_per_hour": snow,
        }

    def test_weather_threshold_boundaries(self):
        cases = [
            (classify_wind, [
                (24.99, "low"),
                (25, "moderate"),
                (34.99, "moderate"),
                (35, "high"),
                (44.99, "high"),
                (45, "severe"),
                (54.99, "severe"),
                (55, "no_travel"),
            ]),
            (classify_rain, [
                (0.099, "low"),
                (0.10, "moderate"),
                (0.249, "moderate"),
                (0.25, "high"),
                (0.499, "high"),
                (0.50, "severe"),
                (1.00, "severe"),
                (1.001, "no_travel"),
            ]),
            (classify_snow, [
                (0.499, "low"),
                (0.5, "moderate"),
                (0.999, "moderate"),
                (1.0, "high"),
                (1.999, "high"),
                (2.0, "severe"),
                (3.0, "severe"),
                (3.001, "no_travel"),
            ]),
        ]

        for classifier, boundaries in cases:
            for value, expected in boundaries:
                with self.subTest(
                    classifier=classifier.__name__, value=value
                ):
                    self.assertEqual(classifier(value), expected)

    def test_load_overrides_use_strict_weight_thresholds(self):
        cases = [
            (45, "30000.00", "severe"),
            (45, "30000.01", "no_travel"),
            (35, "40000.00", "high"),
            (35, "40000.01", "severe"),
            (34.99, "50000.00", "moderate"),
            (55, "0.00", "no_travel"),
        ]

        for wind, load, expected in cases:
            with self.subTest(wind=wind, load=load):
                risk = assess_checkpoint_risk(
                    self.weather(wind=wind),
                    Decimal(load),
                )
                self.assertEqual(risk["severity"], expected)

    def test_load_override_cannot_lower_precipitation_risk(self):
        risk = assess_checkpoint_risk(
            self.weather(wind=40, rain=1.1),
            Decimal("45000"),
        )

        self.assertEqual(risk["load_override"], "severe")
        self.assertEqual(risk["severity"], "no_travel")

    def test_highest_hazard_wins(self):
        risk = assess_checkpoint_risk(
            self.weather(wind=10, rain=0.3, snow=2.5),
            Decimal("10000"),
        )

        self.assertEqual(risk["severity"], "severe")
        self.assertEqual(risk["score"], 3)

    def test_missing_or_invalid_weather_remains_unknown(self):
        cases = [
            {"status": "unknown", "reason": "Provider unavailable."},
            self.weather(wind=None),
            self.weather(rain=float("nan")),
            self.weather(snow=-1),
        ]

        for weather in cases:
            with self.subTest(weather=weather):
                risk = assess_checkpoint_risk(weather, Decimal("10000"))
                self.assertEqual(risk["severity"], "unknown")
                self.assertIsNone(risk["score"])

    def test_load_is_required_and_nonnegative(self):
        payload = {
            "origin": "Chicago",
            "destination": "Indianapolis",
            "departure_time": "2026-10-31T12:00:00Z",
            "sampling_interval_miles": 25,
        }

        missing = RouteRequestSerializer(data=payload)
        self.assertFalse(missing.is_valid())
        self.assertIn("load_weight_lb", missing.errors)

        negative = RouteRequestSerializer(
            data={**payload, "load_weight_lb": "-1"}
        )
        self.assertFalse(negative.is_valid())
        self.assertIn("load_weight_lb", negative.errors)

        empty_truck = RouteRequestSerializer(
            data={**payload, "load_weight_lb": "0"}
        )
        self.assertTrue(empty_truck.is_valid(), empty_truck.errors)


from .services.recommendations import (
    analyze_and_recommend,
    summarize_route,
    ranking_key
)

class RecommendationTests(SimpleTestCase):
    def make_route(self, route_id, levels, miles=None, duration=3600):
        if miles is None:
            miles = [index * 10 for index in range(len(levels))]

        return {
            "id": route_id,
            "duration_seconds": duration,
            "checkpoints": [
                {
                    "id": f"{route_id}-checkpoint-{index}",
                    "distance_from_start_meters": mile * METERS_PER_MILE,
                    "risk": {"severity": level},
                }
                for index, (mile, level) in enumerate(zip(miles, levels))
            ],
        }

    def test_miles_and_average_are_distance_weighted(self):
        route = self.make_route(
            "route-1",
            ["low", "moderate", "severe"],
            miles=[0, 10, 30],
        )

        summary = summarize_route(route)

        self.assertAlmostEqual(summary["risk_miles"]["moderate"], 10)
        self.assertAlmostEqual(summary["risk_miles"]["severe"], 20)
        self.assertAlmostEqual(sum(summary["risk_miles"].values()), 30)
        self.assertAlmostEqual(summary["average_risk"], 70 / 30)

    def test_final_partial_interval_is_counted(self):
        route = self.make_route(
            "route-1",
            ["low", "low", "high"],
            miles=[0, 25, 30],
        )

        summary = summarize_route(route)

        self.assertAlmostEqual(summary["risk_miles"]["low"], 25)
        self.assertAlmostEqual(summary["risk_miles"]["high"], 5)

    def test_ranking_priorities_are_lexicographic(self):
        def candidate(severe, high, average, duration):
            return {
                "duration_seconds": duration,
                "risk_summary": {
                    "risk_miles": {"severe": severe, "high": high},
                    "average_risk": average,
                },
            }

        cases = [
            # Severe miles take priority over everything else.
            (
                candidate(0, 100, 2, 10000),
                candidate(1, 0, 0.1, 100),
            ),
            # High miles take priority over average and time.
            (
                candidate(0, 0, 1, 10000),
                candidate(0, 1, 0.1, 100),
            ),
            # Average risk takes priority over time.
            (
                candidate(0, 0, 0.1, 10000),
                candidate(0, 0, 0.2, 100),
            ),
            # Duration breaks a risk tie.
            (
                candidate(0, 0, 0, 100),
                candidate(0, 0, 0, 200),
            ),
        ]

        for better, worse in cases:
            with self.subTest(better=better, worse=worse):
                self.assertLess(ranking_key(better), ranking_key(worse))

    def test_blocked_and_unknown_routes_are_excluded(self):
        routes = [
            self.make_route("blocked", ["low", "no_travel"], duration=100),
            self.make_route("unknown", ["low", "unknown"], duration=200),
            self.make_route("eligible", ["low", "low"], duration=300),
        ]

        result = analyze_and_recommend(routes)

        self.assertEqual(result["route_id"], "eligible")
        self.assertEqual(result["eligible_route_ids"], ["eligible"])
        self.assertIsNone(routes[0]["rank"])
        self.assertIsNone(routes[1]["risk_summary"]["average_risk"])
        self.assertEqual(routes[2]["rank"], 1)

    def test_all_ineligible_returns_no_recommendation(self):
        routes = [
            self.make_route("blocked", ["no_travel", "no_travel"]),
            self.make_route("unknown", ["unknown", "unknown"]),
        ]

        result = analyze_and_recommend(routes)

        self.assertIsNone(result["route_id"])
        self.assertFalse(any(route["recommended"] for route in routes))

    def test_fastest_route_wins_when_weather_is_equal(self):
        routes = [
            self.make_route("slow", ["low", "low"], duration=5000),
            self.make_route("fast", ["low", "low"], duration=3000),
        ]

        result = analyze_and_recommend(routes)

        self.assertEqual(result["route_id"], "fast")
        self.assertEqual(result["eligible_route_ids"], ["fast", "slow"])
        self.assertIn("shorter travel time", result["reason"])

    def test_exact_tie_preserves_provider_order(self):
        routes = [
            self.make_route("first", ["low", "low"]),
            self.make_route("second", ["low", "low"]),
        ]

        result = analyze_and_recommend(routes)

        self.assertEqual(result["route_id"], "first")
        self.assertIn("tied", result["reason"])