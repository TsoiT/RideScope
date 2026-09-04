import json
import tempfile
import unittest
from pathlib import Path

from ridescope.file_sources import (
    DEFAULT_SETTINGS,
    discover_activity_files,
    display_name_for_file,
    load_settings,
    resolve_folder,
    save_settings,
)


class FileSourceTests(unittest.TestCase):
    def test_discovery_filter_recursion_and_order(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "b.FIT").write_bytes(b"fit")
            (root / "a.gpx").write_bytes(b"gpx")
            (root / "skip.csv").write_text("skip", encoding="utf-8")
            (root / "child").mkdir()
            (root / "child" / "c.gpx").write_bytes(b"gpx")

            flat, warnings = discover_activity_files(root, recursive=False)
            self.assertEqual([path.name for path in flat], ["a.gpx", "b.FIT"])
            self.assertEqual(warnings, [])

            recursive, _ = discover_activity_files(root, recursive=True)
            self.assertEqual(len(recursive), 3)
            self.assertEqual(display_name_for_file(root / "child" / "c.gpx", root), "文件夹/child/c.gpx")

    def test_discovery_limit_and_missing_folder(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for index in range(4):
                (root / f"{index}.gpx").write_bytes(b"x")
            files, warnings = discover_activity_files(root, max_files=2)
            self.assertEqual(len(files), 2)
            self.assertTrue(warnings)
            missing, missing_warnings = discover_activity_files(root / "missing")
            self.assertEqual(missing, [])
            self.assertTrue(missing_warnings)

    def test_settings_round_trip_and_relative_resolution(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            settings_path = root / "settings.json"
            defaults, warning = load_settings(settings_path)
            self.assertEqual(defaults, DEFAULT_SETTINGS)
            self.assertIsNone(warning)

            save_settings(settings_path, {"folder_path": "my-rides", "auto_scan": False, "recursive": False})
            loaded, warning = load_settings(settings_path)
            self.assertEqual(loaded["folder_path"], "my-rides")
            self.assertFalse(loaded["auto_scan"])
            self.assertIsNone(warning)
            self.assertEqual(resolve_folder("my-rides", root), (root / "my-rides").resolve())
            self.assertEqual(json.loads(settings_path.read_text(encoding="utf-8"))["folder_path"], "my-rides")


if __name__ == "__main__":
    unittest.main()
