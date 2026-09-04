"""Plotly 可视化构建函数。"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go


COLORS = ["#22c55e", "#38bdf8", "#f59e0b", "#a78bfa", "#fb7185", "#14b8a6"]


def _map_view(points: pd.DataFrame) -> tuple[dict[str, float], float]:
    center = {
        "lat": float(points["latitude"].median()),
        "lon": float(points["longitude"].median()),
    }
    lat_span = float(points["latitude"].max() - points["latitude"].min())
    lon_span = float(points["longitude"].max() - points["longitude"].min())
    span = max(lat_span, lon_span, 0.0001)
    zoom = float(np.clip(math.log2(360.0 / span) - 1.2, 1.0, 17.0))
    return center, zoom


def osm_route_figure(points: pd.DataFrame) -> go.Figure:
    """使用免密钥的 OpenStreetMap 瓦片绘制线路。"""
    center, zoom = _map_view(points)
    fig = go.Figure()
    for index, (name, group) in enumerate(points.groupby("file_name", sort=False)):
        fig.add_trace(
            go.Scattermap(
                lat=group["latitude"],
                lon=group["longitude"],
                mode="lines",
                name=name,
                line={"width": 4, "color": COLORS[index % len(COLORS)]},
                hovertemplate=f"{name}<br>经度 %{{lon:.5f}}<br>纬度 %{{lat:.5f}}<extra></extra>",
            )
        )
    fig.update_layout(
        template="plotly_dark",
        height=570,
        margin={"l": 0, "r": 0, "t": 38, "b": 0},
        title="轨迹线路图（OpenStreetMap）",
        legend={"orientation": "h", "y": 1.02, "x": 0},
        map={"style": "open-street-map", "center": center, "zoom": zoom},
        paper_bgcolor="#07111f",
    )
    return fig


def _combined_route_coordinates(points: pd.DataFrame) -> tuple[list[float | None], list[float | None]]:
    """合并多条线路，并用 None 防止不同骑行之间被错误连线。"""
    latitudes: list[float | None] = []
    longitudes: list[float | None] = []
    for _, group in points.groupby("file_name", sort=False):
        latitudes.extend(group["latitude"].astype(float).tolist())
        longitudes.extend(group["longitude"].astype(float).tolist())
        latitudes.append(None)
        longitudes.append(None)
    return latitudes, longitudes


def osm_track_overview_figure(points: pd.DataFrame) -> go.Figure:
    """在 OpenStreetMap 上仅绘制全部轨迹，不使用遮挡地图的密度色块。"""
    center, zoom = _map_view(points)
    latitudes, longitudes = _combined_route_coordinates(points)
    fig = go.Figure(
        go.Scattermap(
            lat=latitudes,
            lon=longitudes,
            mode="lines",
            line={"width": 2.2, "color": "#ef4444"},
            opacity=0.82,
            hoverinfo="skip",
            showlegend=False,
        )
    )
    fig.update_layout(
        template="plotly_dark",
        height=570,
        title="全部骑行轨迹总览（OpenStreetMap）",
        margin={"l": 0, "r": 0, "t": 38, "b": 0},
        map={"style": "open-street-map", "center": center, "zoom": zoom},
        paper_bgcolor="#07111f",
        showlegend=False,
    )
    return fig


def route_figure(points: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    for index, (name, group) in enumerate(points.groupby("file_name", sort=False)):
        fig.add_trace(
            go.Scattergl(
                x=group["longitude"],
                y=group["latitude"],
                mode="lines",
                name=name,
                line={"width": 3, "color": COLORS[index % len(COLORS)]},
                hovertemplate=f"{name}<br>经度 %{{x:.5f}}<br>纬度 %{{y:.5f}}<extra></extra>",
            )
        )
    fig.update_layout(
        template="plotly_dark",
        height=570,
        margin={"l": 10, "r": 10, "t": 38, "b": 10},
        title="轨迹线路图（离线坐标视图）",
        legend={"orientation": "h", "y": 1.02, "x": 0},
        xaxis_title="经度",
        yaxis_title="纬度",
        paper_bgcolor="#07111f",
        plot_bgcolor="#0b1728",
    )
    return fig


def track_overview_figure(points: pd.DataFrame) -> go.Figure:
    """离线全部轨迹总览，仅绘制细线。"""
    latitudes, longitudes = _combined_route_coordinates(points)
    fig = go.Figure(
        go.Scattergl(
            x=longitudes,
            y=latitudes,
            mode="lines",
            line={"width": 2, "color": "#ef4444"},
            opacity=0.82,
            hoverinfo="skip",
            showlegend=False,
        )
    )
    fig.update_layout(
        template="plotly_dark",
        height=570,
        title="全部骑行轨迹总览（离线坐标视图）",
        margin={"l": 10, "r": 10, "t": 38, "b": 10},
        xaxis_title="经度",
        yaxis_title="纬度",
        paper_bgcolor="#07111f",
        plot_bgcolor="#0b1728",
    )
    return fig


def profile_figure(points: pd.DataFrame) -> go.Figure:
    long = points[["distance_km", "elevation_m", "speed_kmh"]].melt(
        "distance_km",
        value_vars=["elevation_m", "speed_kmh"],
        var_name="指标",
        value_name="数值",
    )
    long["指标"] = long["指标"].map({"elevation_m": "海拔(m)", "speed_kmh": "速度(km/h)"})
    fig = px.line(long, x="distance_km", y="数值", color="指标", facet_row="指标", color_discrete_sequence=["#38bdf8", "#22c55e"])
    fig.update_yaxes(matches=None)
    fig.update_layout(
        template="plotly_dark",
        height=520,
        margin={"l": 10, "r": 10, "t": 25, "b": 10},
        xaxis_title="累计距离(km)",
        paper_bgcolor="#07111f",
        plot_bgcolor="#0b1728",
        showlegend=False,
    )
    for annotation in fig.layout.annotations:
        annotation.text = annotation.text.split("=")[-1]
    return fig
