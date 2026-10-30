from datetime import datetime, timezone

from django.test import SimpleTestCase

from .services.checkpoints import METERS_PER_MILE, build_checkpoints


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