"""生成不含真实个人位置的合成 GPX 演示数据。"""

from datetime import datetime, timedelta, timezone
from math import cos, pi, sin
from pathlib import Path


def main() -> None:
    output = Path(__file__).with_name("demo_loop.gpx")
    start = datetime(2026, 8, 20, 7, 30, tzinfo=timezone.utc)
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<gpx version="1.1" creator="RideScope" xmlns="http://www.topografix.com/GPX/1/1" xmlns:gpxtpx="http://www.garmin.com/xmlschemas/TrackPointExtension/v1">',
        "  <trk><name>RideScope 示例环线</name><trkseg>",
    ]
    center_lat, center_lon = 39.9630, 116.3570
    for i in range(181):
        angle = 2 * pi * i / 180
        lat = center_lat + 0.020 * sin(angle) + 0.0025 * sin(3 * angle)
        lon = center_lon + 0.030 * cos(angle) + 0.0020 * cos(2 * angle)
        elevation = 42 + 18 * sin(2 * angle) + 6 * sin(5 * angle)
        timestamp = start + timedelta(seconds=15 * i)
        heart_rate = round(125 + 18 * sin(angle - 0.6) + 7 * sin(4 * angle))
        cadence = round(78 + 9 * sin(3 * angle))
        speed_mps = 6.2 + 1.1 * sin(2 * angle + 0.4)
        lines.extend(
            [
                f'    <trkpt lat="{lat:.7f}" lon="{lon:.7f}">',
                f"      <ele>{elevation:.1f}</ele>",
                f"      <time>{timestamp.isoformat().replace('+00:00', 'Z')}</time>",
                "      <extensions><gpxtpx:TrackPointExtension>",
                f"        <gpxtpx:hr>{heart_rate}</gpxtpx:hr><gpxtpx:cad>{cadence}</gpxtpx:cad>",
                f"        <speed>{speed_mps:.2f}</speed>",
                "      </gpxtpx:TrackPointExtension></extensions>",
                "    </trkpt>",
            ]
        )
    lines.extend(["  </trkseg></trk>", "</gpx>"])
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()

