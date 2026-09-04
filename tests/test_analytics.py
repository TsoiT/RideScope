import unittest

import numpy as np
import pandas as pd

from ridescope.analytics import build_track, haversine_m, summarize_track


class AnalyticsTests(unittest.TestCase):
    def test_haversine_one_degree_at_equator(self):
        distance = haversine_m(np.array([0.0]), np.array([0.0]), np.array([0.0]), np.array([1.0]))[0]
        self.assertAlmostEqual(distance / 1000.0, 111.195, places=2)

    def test_build_and_summary(self):
        raw = pd.DataFrame(
            {
                "file_name": ["a.gpx"] * 3,
                "track_name": ["A"] * 3,
                "segment_id": ["1-1"] * 3,
                "point_index": [1, 2, 3],
                "latitude": [39.9, 39.9009, 39.9018],
                "longitude": [116.3, 116.3, 116.3],
                "elevation_m": [40, 45, 43],
                "timestamp": pd.to_datetime(["2026-08-01T00:00:00Z", "2026-08-01T00:00:20Z", "2026-08-01T00:00:40Z"]),
                "speed_kmh_source": [np.nan, np.nan, np.nan],
                "heart_rate_bpm": [100, 120, 130],
                "cadence_rpm": [70, 80, 90],
                "power_w": [100, 150, 200],
            }
        )
        track = build_track(raw)
        summary = summarize_track(track)
        self.assertGreater(summary["距离(km)"], 0.19)
        self.assertAlmostEqual(summary["累计爬升(m)"], 5.0)
        self.assertEqual(summary["轨迹点数"], 3)


if __name__ == "__main__":
    unittest.main()

