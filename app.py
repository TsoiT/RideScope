from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd
import streamlit as st

from ridescope import ParseError, build_track, parse_activity, summarize_tracks
from ridescope.file_sources import (
    discover_activity_files,
    display_name_for_file,
    load_settings,
    resolve_folder,
    save_settings,
)
from ridescope.platforms import (
    IGPSportClient,
    OnelapClient,
    PlatformError,
    save_downloaded_activity,
)
from ridescope.visuals import (
    osm_route_figure,
    osm_track_overview_figure,
    profile_figure,
    route_figure,
    track_overview_figure,
)


ROOT = Path(__file__).resolve().parent
SAMPLE = ROOT / "sample_data" / "demo_loop.gpx"
SETTINGS_FILE = ROOT / ".ridescope-settings.json"

st.set_page_config(page_title="RideScope 骑行轨迹分析", page_icon="🚴", layout="wide")
st.markdown(
    """
    <style>
      .stApp { background: linear-gradient(135deg,#050b14 0%,#071827 55%,#06131c 100%); }
      [data-testid="stMetric"] { background:#0d1d2d; border:1px solid #17354c; border-radius:14px; padding:14px 16px; }
      [data-testid="stMetricLabel"], [data-testid="stMetricLabel"] * { color:#a9bfd2 !important; }
      [data-testid="stMetricValue"], [data-testid="stMetricValue"] * { color:#ecfdf5 !important; font-size:1.55rem !important; }
      .hero { padding: 12px 0 4px; }
      .hero h1 { margin:0; color:#f8fafc; font-size:2.15rem; }
      .hero p { color:#9fb4c8; margin-top:8px; }
      .notice { background:#0e2536; border-left:4px solid #22c55e; padding:10px 14px; border-radius:8px; color:#d7e9f6; }
    </style>
    <div class="hero"><h1>RideScope 骑行轨迹分析</h1><p>把 GPX / FIT 变成可读的里程、速度、爬升和轨迹总览。</p></div>
    """,
    unsafe_allow_html=True,
)


@st.cache_data(show_spinner=False)
def load_files(items: tuple[tuple[str, bytes], ...]) -> tuple[pd.DataFrame, list[str]]:
    frames: list[pd.DataFrame] = []
    errors: list[str] = []
    for name, data in items:
        try:
            frames.append(parse_activity(data, name))
        except (ParseError, ValueError) as exc:
            errors.append(str(exc))
    if not frames:
        return pd.DataFrame(), errors
    try:
        return build_track(pd.concat(frames, ignore_index=True)), errors
    except ValueError as exc:
        errors.append(str(exc))
        return pd.DataFrame(), errors


@st.cache_data(show_spinner=False)
def read_local_activity(path_text: str, modified_ns: int, size: int) -> bytes:
    """按路径和文件状态缓存读取结果，文件变化后自动失效。"""
    del modified_ns, size
    return Path(path_text).read_bytes()


saved_settings, settings_warning = load_settings(SETTINGS_FILE)
if "remote_items" not in st.session_state:
    st.session_state["remote_items"] = []


with st.sidebar:
    st.header("导入轨迹")
    uploaded = st.file_uploader("选择一个或多个文件", type=["gpx", "fit"], accept_multiple_files=True)
    with st.expander("自动从 iGPSPORT / Onelap 下载"):
        platform_name = st.selectbox("运动平台", ["iGPSPORT（中国大陆）", "Onelap / 顽鹿 OTM"])
        login_mode = "账号密码"
        if platform_name.startswith("iGPSPORT"):
            login_mode = st.radio("登录方式", ["账号密码", "访问令牌"], horizontal=True)

        with st.form("platform_download_form"):
            account = ""
            password = ""
            access_token = ""
            if login_mode == "访问令牌":
                access_token = st.text_input("iGPSPORT Access Token", type="password")
                st.caption("可填写网页端 Authorization 中 Bearer 后面的内容。")
            else:
                account_label = "手机号 / 用户名" if platform_name.startswith("iGPSPORT") else "Onelap 手机号 / 账号"
                account = st.text_input(account_label)
                password = st.text_input("密码", type="password")
            record_limit = st.number_input("下载最近记录数", min_value=1, max_value=1000, value=100, step=10)
            save_to_records = st.checkbox("同时保存到项目 records 文件夹", value=True)
            fetch_submitted = st.form_submit_button("登录、获取并下载", width="stretch")

        if fetch_submitted:
            if login_mode == "访问令牌" and not access_token.strip():
                st.error("请填写访问令牌。")
            elif login_mode != "访问令牌" and (not account.strip() or not password):
                st.error("请填写账号和密码。")
            else:
                client = IGPSportClient() if platform_name.startswith("iGPSPORT") else OnelapClient()
                try:
                    with st.spinner("正在登录并读取骑行列表……"):
                        token = access_token.strip() if login_mode == "访问令牌" else client.login(account, password)
                        activities = client.list_activities(token, record_limit)
                    if not activities:
                        st.info("平台没有返回可下载的骑行记录。")
                    else:
                        progress = st.progress(0, text="准备下载……")
                        downloaded: list[tuple[str, bytes]] = []
                        saved_count = 0
                        failures: list[str] = []
                        for index, activity in enumerate(activities, start=1):
                            progress.progress(
                                (index - 1) / len(activities),
                                text=f"正在下载 {index}/{len(activities)}：{activity.label()}",
                            )
                            try:
                                data = client.download_activity(token, activity)
                                display_name = f"平台/{activity.platform}/{activity.filename()}"
                                downloaded.append((display_name, data))
                                if save_to_records:
                                    save_downloaded_activity(ROOT, activity, data)
                                    saved_count += 1
                            except (PlatformError, OSError) as exc:
                                failures.append(f"{activity.label()}：{exc}")
                        progress.progress(1.0, text="平台下载完成")
                        progress.empty()

                        existing = {name: data for name, data in st.session_state["remote_items"]}
                        existing.update(downloaded)
                        st.session_state["remote_items"] = list(existing.items())
                        if downloaded:
                            saved_text = f"，其中 {saved_count} 个已保存到 records" if save_to_records else ""
                            st.success(f"成功获取 {len(downloaded)} 个 FIT 文件{saved_text}。")
                        for failure in failures[:5]:
                            st.warning(failure)
                        if len(failures) > 5:
                            st.warning(f"另有 {len(failures) - 5} 个文件下载失败。")
                except PlatformError as exc:
                    st.error(str(exc))

        if st.session_state["remote_items"]:
            st.caption(f"当前会话已载入 {len(st.session_state['remote_items'])} 个平台文件。")
            if st.button("清除本次会话的平台数据", width="stretch"):
                st.session_state["remote_items"] = []
                st.rerun()
        st.caption("账号、密码和 Token 仅用于本次请求，不会写入设置文件。平台网页接口变化时可能需要更新连接器。")
    use_sample = st.toggle("没有文件时使用示例轨迹", value=True)
    st.caption("文件只在当前电脑内存中处理，不会上传到第三方服务。")
    st.divider()
    st.markdown("**自动读取文件夹**")
    folder_text = st.text_input(
        "轨迹文件夹路径",
        value=saved_settings["folder_path"],
        help="相对路径从 RideScope 项目目录开始计算；也可以填写 D:\\骑行记录 这样的完整路径。",
    )
    auto_scan = st.toggle("启动及刷新页面时自动读取", value=saved_settings["auto_scan"])
    recursive_scan = st.toggle("同时扫描子文件夹", value=saved_settings["recursive"])
    if st.button("保存文件夹设置", width="stretch"):
        try:
            save_settings(
                SETTINGS_FILE,
                {"folder_path": folder_text, "auto_scan": auto_scan, "recursive": recursive_scan},
            )
            st.success("设置已保存，下次启动会继续使用。")
        except OSError as exc:
            st.error(f"设置保存失败：{exc}")
    if settings_warning:
        st.warning(settings_warning)
    st.divider()
    map_mode = st.radio(
        "地图模式",
        ["在线 OpenStreetMap", "离线坐标图"],
        help="在线地图可显示道路和地名，但需要电脑能够访问互联网。",
    )
    st.divider()
    st.markdown("**统计口径**")
    st.caption("移动速度阈值 1 km/h；相邻记录超过 10 分钟不计入移动时间；异常速度上限 150 km/h。")

items: list[tuple[str, bytes]] = []
seen_content: set[str] = set()
folder_file_count = 0
duplicate_count = 0
source_warnings: list[str] = []


def add_item(name: str, data: bytes) -> None:
    global duplicate_count
    fingerprint = hashlib.sha256(data).hexdigest()
    if fingerprint in seen_content:
        duplicate_count += 1
        return
    seen_content.add(fingerprint)
    items.append((name, data))


if uploaded:
    for file in uploaded:
        add_item(f"上传/{file.name}", file.getvalue())

for name, data in st.session_state["remote_items"]:
    add_item(name, data)

if auto_scan:
    try:
        scan_folder = resolve_folder(folder_text, ROOT)
        folder_files, folder_warnings = discover_activity_files(scan_folder, recursive_scan)
        source_warnings.extend(folder_warnings)
        for path in folder_files:
            try:
                stat = path.stat()
                data = read_local_activity(str(path), stat.st_mtime_ns, stat.st_size)
                before = len(items)
                add_item(display_name_for_file(path, scan_folder), data)
                if len(items) > before:
                    folder_file_count += 1
            except (OSError, PermissionError) as exc:
                source_warnings.append(f"无法读取 {path}：{exc}")
    except (OSError, RuntimeError) as exc:
        source_warnings.append(f"轨迹文件夹路径无法使用：{exc}")

using_sample = False
if not items and use_sample and SAMPLE.exists():
    add_item(SAMPLE.name, SAMPLE.read_bytes())
    using_sample = True

if auto_scan:
    if folder_file_count:
        st.sidebar.success(f"已从文件夹读取 {folder_file_count} 个轨迹文件。")
    elif not source_warnings:
        st.sidebar.info("文件夹中没有找到 GPX / FIT 文件。")
if duplicate_count:
    st.sidebar.caption(f"已跳过 {duplicate_count} 个内容相同的重复文件。")
for warning in source_warnings:
    st.sidebar.warning(warning)

if not items:
    st.info("请在左侧导入 GPX 或 FIT 文件。也可以开启示例轨迹快速体验。")
    st.stop()

points, errors = load_files(tuple(items))
for error in errors:
    st.warning(error)
if points.empty:
    st.error("没有可分析的有效轨迹。请检查文件内容后重试。")
    st.stop()

if using_sample:
    st.markdown('<div class="notice">当前显示内置示例数据；导入自己的 GPX / FIT 后会自动替换。</div>', unsafe_allow_html=True)

summary = summarize_tracks(points)
total_distance = summary["距离(km)"].sum()
total_gain = summary["累计爬升(m)"].sum()
moving_hours = summary["运动时间(h)"].sum(min_count=1)
overall_avg = total_distance / moving_hours if pd.notna(moving_hours) and moving_hours > 0 else float("nan")

cols = st.columns(5, gap="small")
cols[0].metric("骑行次数", f"{len(summary)}")
cols[1].metric("总里程", f"{total_distance:.2f} km")
cols[2].metric("累计爬升", f"{total_gain:.0f} m")
cols[3].metric("运动时间", f"{moving_hours:.2f} h" if pd.notna(moving_hours) else "--")
cols[4].metric("综合均速", f"{overall_avg:.1f} km/h" if pd.notna(overall_avg) else "--")

tab_map, tab_overview, tab_profile, tab_data = st.tabs(["线路", "轨迹总览", "曲线", "数据与导出"])
with tab_map:
    if map_mode == "在线 OpenStreetMap":
        st.plotly_chart(osm_route_figure(points), width="stretch")
        st.caption("道路和地名来自 OpenStreetMap，需要联网加载；若底图无法显示，可在左侧切换到离线坐标图。")
    else:
        st.plotly_chart(route_figure(points), width="stretch")
        st.caption("离线坐标视图不依赖地图瓦片；横纵轴分别为经度、纬度。")

with tab_overview:
    if map_mode == "在线 OpenStreetMap":
        st.plotly_chart(osm_track_overview_figure(points), width="stretch")
        st.caption("只绘制全部骑行的细轨迹线，不再使用会遮挡道路和地名的密度色块。")
    else:
        st.plotly_chart(track_overview_figure(points), width="stretch")
        st.caption("离线模式只显示经纬度轨迹线，不依赖地图瓦片。")

with tab_profile:
    selected = st.selectbox("选择一次骑行", summary["文件"].tolist())
    selected_points = points.loc[points["file_name"] == selected]
    st.plotly_chart(profile_figure(selected_points), width="stretch")

with tab_data:
    display = summary.copy()
    numeric_columns = display.select_dtypes(include="number").columns
    display[numeric_columns] = display[numeric_columns].round(2)
    display["开始时间"] = display["开始时间"].dt.strftime("%Y-%m-%d %H:%M:%S UTC")
    st.dataframe(display, width="stretch", hide_index=True)
    left, right = st.columns(2)
    left.download_button(
        "下载骑行汇总 CSV",
        summary.to_csv(index=False).encode("utf-8-sig"),
        "ridescope_summary.csv",
        "text/csv",
        width="stretch",
    )
    export_columns = [
        "file_name", "track_name", "timestamp", "latitude", "longitude", "elevation_m",
        "distance_km", "speed_kmh", "heart_rate_bpm", "cadence_rpm", "power_w",
    ]
    right.download_button(
        "下载轨迹点 CSV",
        points[export_columns].to_csv(index=False).encode("utf-8-sig"),
        "ridescope_points.csv",
        "text/csv",
        width="stretch",
    )

st.caption("RideScope · 本地数据处理 · GPX / FIT · 课程设计演示版")
