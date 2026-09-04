import unittest
from pathlib import Path

from ridescope.analytics import build_track
from ridescope.parsers import parse_activity
from ridescope.visuals import osm_track_overview_figure, track_overview_figure


ROOT = Path(__file__).resolve().parents[1]


class VisualTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = ROOT / "sample_data" / "demo_loop.gpx"
        cls.points = build_track(parse_activity(path.read_bytes(), path.name))

    def test_online_overview_contains_only_route_lines(self):
        figure = osm_track_overview_figure(self.points)
        self.assertEqual(len(figure.data), 1)
        self.assertEqual(figure.data[0].type, "scattermap")
        self.assertEqual(figure.data[0].mode, "lines")
        self.assertNotIn("densitymap", {trace.type for trace in figure.data})

    def test_offline_overview_contains_only_route_lines(self):
        figure = track_overview_figure(self.points)
        self.assertEqual(len(figure.data), 1)
        self.assertEqual(figure.data[0].type, "scattergl")
        self.assertEqual(figure.data[0].mode, "lines")


if __name__ == "__main__":
    unittest.main()
