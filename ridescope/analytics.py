"""轨迹清洗、派生指标与骑行摘要统计。"""

from __future__ import annotations

import numpy as np
import pandas as pd


EARTH_RADIUS_M = 6_371_008.8
MOVING_THRESHOLD_KMH = 1.0
MAX_REASONABLE_SPEED_KMH = 150.0
MAX_GAP_SECONDS = 600.0


def haversine_m(lat1, lon1, lat2, lon2):
    """向量化 Haversine 球面距离，单位为米。"""
    lat1 = np.radians(lat1)
    lon1 = np.radians(lon1)
    lat2 = np.radians(lat2)
    lon2 = np.radians(lon2)
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat / 2.0) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2.0) ** 2
    return 2.0 * EARTH_RADIUS_M * np.arcsin(np.sqrt(np.clip(a, 0.0, 1.0)))


def build_track(raw: pd.DataFrame) -> pd.DataFrame:
    """清洗统一数据并计算距离、时间、速度、爬升等派生列。"""
    if raw.empty:
        raise ValueError("轨迹点为空。")
    df = raw.copy().reset_index(drop=True)
    valid = (
        df["latitude"].between(-90, 90)
        & df["longitude"].between(-180, 180)
        & df[["latitude", "longitude"]].notna().all(axis=1)
    )
    df = df.loc[valid].reset_index(drop=True)
    if len(df) < 2:
        raise ValueError("至少需要两个有效轨迹点。")

    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
    prev = df.shift(1)
    same_segment = (df["file_name"] == prev["file_name"]) & (df["segment_id"] == prev["segment_id"])
    step = haversine_m(
        prev["latitude"].to_numpy(float),
        prev["longitude"].to_numpy(float),
        df["latitude"].to_numpy(float),
        df["longitude"].to_numpy(float),
    )
    df["distance_step_m"] = np.where(same_segment, np.nan_to_num(step, nan=0.0), 0.0)

    dt = (df["timestamp"] - prev["timestamp"]).dt.total_seconds()
    dt = dt.where(same_segment & dt.gt(0) & dt.le(MAX_GAP_SECONDS))
    df["time_step_s"] = dt.fillna(0.0)
    calculated_speed = (df["distance_step_m"] / dt) * 3.6
    source_speed = pd.to_numeric(df.get("speed_kmh_source"), errors="coerce")
    speed = source_speed.combine_first(calculated_speed)
    df["speed_kmh"] = speed.where(speed.between(0, MAX_REASONABLE_SPEED_KMH))

    df["distance_km"] = df.groupby("file_name")["distance_step_m"].cumsum() / 1000.0
    first_time = df.groupby("file_name")["timestamp"].transform("min")
    df["elapsed_s"] = (df["timestamp"] - first_time).dt.total_seconds()

    elevation = pd.to_numeric(df["elevation_m"], errors="coerce")
    elevation_delta = elevation - elevation.shift(1)
    plausible_climb = elevation_delta.where(same_segment & elevation_delta.between(0, 50), 0.0)
    df["elevation_gain_step_m"] = plausible_climb.fillna(0.0)
    return df


def summarize_track(track: pd.DataFrame, file_name: str | None = None) -> dict:
    if file_name is not None:
        track = track.loc[track["file_name"] == file_name]
    if track.empty:
        raise ValueError("没有可汇总的轨迹点。")

    distance_km = float(track["distance_step_m"].sum() / 1000.0)
    valid_time = track["timestamp"].dropna()
    duration_s = float((valid_time.max() - valid_time.min()).total_seconds()) if len(valid_time) >= 2 else np.nan
    moving_mask = track["speed_kmh"].ge(MOVING_THRESHOLD_KMH) & track["time_step_s"].gt(0)
    moving_time_s = float(track.loc[moving_mask, "time_step_s"].sum())
    avg_speed = distance_km / (moving_time_s / 3600.0) if moving_time_s > 0 else np.nan
    start = valid_time.min() if not valid_time.empty else pd.NaT

    return {
        "文件": str(track["file_name"].iloc[0]),
        "轨迹名称": str(track["track_name"].iloc[0]),
        "开始时间": start,
        "距离(km)": distance_km,
        "总用时(h)": duration_s / 3600.0 if np.isfinite(duration_s) else np.nan,
        "运动时间(h)": moving_time_s / 3600.0 if moving_time_s > 0 else np.nan,
        "平均速度(km/h)": avg_speed,
        "最高速度(km/h)": float(track["speed_kmh"].max()) if track["speed_kmh"].notna().any() else np.nan,
        "累计爬升(m)": float(track["elevation_gain_step_m"].sum()),
        "平均心率(bpm)": float(track["heart_rate_bpm"].mean()) if track["heart_rate_bpm"].notna().any() else np.nan,
        "平均踏频(rpm)": float(track["cadence_rpm"].mean()) if track["cadence_rpm"].notna().any() else np.nan,
        "平均功率(W)": float(track["power_w"].mean()) if track["power_w"].notna().any() else np.nan,
        "轨迹点数": int(len(track)),
    }


def summarize_tracks(track: pd.DataFrame) -> pd.DataFrame:
    rows = [summarize_track(track, name) for name in track["file_name"].drop_duplicates()]
    return pd.DataFrame(rows)

