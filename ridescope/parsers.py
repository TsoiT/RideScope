"""GPX 与 FIT 轨迹文件解析。"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import BinaryIO
import xml.etree.ElementTree as ET

import pandas as pd


SEMICIRCLES_TO_DEGREES = 180.0 / (2**31)


class ParseError(ValueError):
    """轨迹文件无法解析时抛出的可读错误。"""


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _child_text(element: ET.Element, name: str) -> str | None:
    for child in element:
        if _local_name(child.tag) == name:
            return child.text
    return None


def _descendant_number(element: ET.Element, candidates: set[str]) -> float | None:
    for node in element.iter():
        if _local_name(node.tag).lower() in candidates and node.text:
            try:
                return float(node.text)
            except (TypeError, ValueError):
                continue
    return None


def parse_gpx(data: bytes, file_name: str) -> pd.DataFrame:
    try:
        root = ET.fromstring(data)
    except ET.ParseError as exc:
        raise ParseError(f"{file_name} 不是有效的 GPX/XML 文件：{exc}") from exc

    rows: list[dict] = []
    track_index = 0
    for track in (node for node in root.iter() if _local_name(node.tag) == "trk"):
        track_index += 1
        track_name = _child_text(track, "name") or Path(file_name).stem
        segment_index = 0
        for segment in (node for node in track if _local_name(node.tag) == "trkseg"):
            segment_index += 1
            point_index = 0
            for point in (node for node in segment if _local_name(node.tag) == "trkpt"):
                point_index += 1
                try:
                    latitude = float(point.attrib["lat"])
                    longitude = float(point.attrib["lon"])
                except (KeyError, TypeError, ValueError) as exc:
                    raise ParseError(f"{file_name} 中存在缺少经纬度的轨迹点。") from exc
                rows.append(
                    {
                        "file_name": file_name,
                        "track_name": track_name,
                        "segment_id": f"{track_index}-{segment_index}",
                        "point_index": point_index,
                        "latitude": latitude,
                        "longitude": longitude,
                        "elevation_m": _to_float(_child_text(point, "ele")),
                        "timestamp": pd.to_datetime(_child_text(point, "time"), utc=True, errors="coerce"),
                        "speed_kmh_source": _speed_to_kmh(
                            _descendant_number(point, {"speed"})
                        ),
                        "heart_rate_bpm": _descendant_number(point, {"hr", "heartrate"}),
                        "cadence_rpm": _descendant_number(point, {"cad", "cadence"}),
                        "power_w": _descendant_number(point, {"power", "watts"}),
                    }
                )

    if not rows:
        raise ParseError(f"{file_name} 中没有找到 GPX 轨迹点（trkpt）。")
    return pd.DataFrame(rows)


def parse_fit(data: bytes, file_name: str) -> pd.DataFrame:
    try:
        from fitparse import FitFile
    except ImportError as exc:
        raise ParseError("读取 FIT 需要安装 fitparse，请重新运行启动脚本安装依赖。") from exc

    try:
        fit_file = FitFile(BytesIO(data))
        rows: list[dict] = []
        for point_index, record in enumerate(fit_file.get_messages("record"), start=1):
            values = record.get_values()
            lat = values.get("position_lat")
            lon = values.get("position_long")
            if lat is None or lon is None:
                continue
            speed = values.get("enhanced_speed", values.get("speed"))
            elevation = values.get("enhanced_altitude", values.get("altitude"))
            rows.append(
                {
                    "file_name": file_name,
                    "track_name": Path(file_name).stem,
                    "segment_id": "1-1",
                    "point_index": point_index,
                    "latitude": float(lat) * SEMICIRCLES_TO_DEGREES,
                    "longitude": float(lon) * SEMICIRCLES_TO_DEGREES,
                    "elevation_m": _to_float(elevation),
                    "timestamp": pd.to_datetime(values.get("timestamp"), utc=True, errors="coerce"),
                    "speed_kmh_source": _speed_to_kmh(speed),
                    "heart_rate_bpm": _to_float(values.get("heart_rate")),
                    "cadence_rpm": _to_float(values.get("cadence")),
                    "power_w": _to_float(values.get("power")),
                }
            )
    except Exception as exc:
        raise ParseError(f"{file_name} 不是有效的 FIT 文件：{exc}") from exc

    if not rows:
        raise ParseError(f"{file_name} 中没有带经纬度的 FIT record 记录。")
    return pd.DataFrame(rows)


def parse_activity(source: bytes | BinaryIO, file_name: str) -> pd.DataFrame:
    """按照扩展名解析轨迹文件，返回统一字段的数据表。"""
    data = source if isinstance(source, bytes) else source.read()
    suffix = Path(file_name).suffix.lower()
    if suffix == ".gpx":
        return parse_gpx(data, file_name)
    if suffix == ".fit":
        return parse_fit(data, file_name)
    raise ParseError(f"暂不支持 {suffix or '无扩展名'} 文件，请选择 .gpx 或 .fit。")


def _to_float(value) -> float | None:
    try:
        return None if value is None else float(value)
    except (TypeError, ValueError):
        return None


def _speed_to_kmh(speed_mps) -> float | None:
    value = _to_float(speed_mps)
    return None if value is None else value * 3.6

