import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from ridescope.parsers import ParseError, parse_activity


ROOT = Path(__file__).resolve().parents[1]


class ParserTests(unittest.TestCase):
    def test_parse_sample_gpx(self):
        path = ROOT / "sample_data" / "demo_loop.gpx"
        frame = parse_activity(path.read_bytes(), path.name)
        self.assertGreater(len(frame), 100)
        self.assertTrue(frame["latitude"].between(-90, 90).all())

    def test_reject_unknown_extension(self):
        with self.assertRaises(ParseError):
            parse_activity(b"data", "track.csv")

    def test_fit_record_field_mapping(self):
        class FakeRecord:
            def get_values(self):
                return {
                    "position_lat": 2**30,
                    "position_long": -(2**30),
                    "enhanced_altitude": 123.4,
                    "enhanced_speed": 10.0,
                    "heart_rate": 145,
                    "cadence": 82,
                    "power": 210,
                    "timestamp": "2026-08-20T08:00:00Z",
                }

        class FakeFitFile:
            def __init__(self, _source):
                pass

            def get_messages(self, name):
                self.name = name
                return [FakeRecord()]

        fake_module = SimpleNamespace(FitFile=FakeFitFile)
        with patch.dict("sys.modules", {"fitparse": fake_module}):
            frame = parse_activity(b"synthetic-fit", "ride.fit")
        self.assertAlmostEqual(frame.loc[0, "latitude"], 90.0)
        self.assertAlmostEqual(frame.loc[0, "longitude"], -90.0)
        self.assertAlmostEqual(frame.loc[0, "speed_kmh_source"], 36.0)
        self.assertEqual(frame.loc[0, "heart_rate_bpm"], 145.0)


if __name__ == "__main__":
    unittest.main()
