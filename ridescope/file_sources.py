"""本地轨迹文件夹发现与用户设置。"""

from __future__ import annotations

import json
from pathlib import Path


SUPPORTED_SUFFIXES = {".gpx", ".fit"}
DEFAULT_SETTINGS = {
    "folder_path": "records",
    "auto_scan": True,
    "recursive": True,
}


def load_settings(path: Path) -> tuple[dict, str | None]:
    """读取本地设置；文件损坏时回退为默认值并返回提示。"""
    settings = DEFAULT_SETTINGS.copy()
    if not path.exists():
        return settings, None
    try:
        saved = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(saved, dict):
            raise ValueError("设置内容不是对象")
        if isinstance(saved.get("folder_path"), str):
            settings["folder_path"] = saved["folder_path"]
        if isinstance(saved.get("auto_scan"), bool):
            settings["auto_scan"] = saved["auto_scan"]
        if isinstance(saved.get("recursive"), bool):
            settings["recursive"] = saved["recursive"]
        return settings, None
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        return settings, f"设置文件无法读取，已使用默认设置：{exc}"


def save_settings(path: Path, settings: dict) -> None:
    """仅保存允许持久化的三个设置字段。"""
    clean = {
        "folder_path": str(settings.get("folder_path", "records")).strip() or "records",
        "auto_scan": bool(settings.get("auto_scan", True)),
        "recursive": bool(settings.get("recursive", True)),
    }
    path.write_text(json.dumps(clean, ensure_ascii=False, indent=2), encoding="utf-8")


def resolve_folder(folder_text: str, project_root: Path) -> Path:
    """把相对路径按项目根目录解析，并兼容用户目录写法。"""
    folder = Path(folder_text.strip() or "records").expanduser()
    if not folder.is_absolute():
        folder = project_root / folder
    return folder.resolve()


def discover_activity_files(
    folder: Path,
    recursive: bool = True,
    max_files: int = 500,
) -> tuple[list[Path], list[str]]:
    """发现目录中的 GPX/FIT 文件，返回有序列表及可读提示。"""
    if not folder.exists():
        return [], [f"轨迹文件夹不存在：{folder}"]
    if not folder.is_dir():
        return [], [f"轨迹文件夹路径不是文件夹：{folder}"]

    warnings: list[str] = []
    try:
        candidates = folder.rglob("*") if recursive else folder.glob("*")
        files = sorted(
            (path for path in candidates if path.is_file() and path.suffix.lower() in SUPPORTED_SUFFIXES),
            key=lambda path: str(path).casefold(),
        )
    except (OSError, PermissionError) as exc:
        return [], [f"无法读取轨迹文件夹 {folder}：{exc}"]

    limit = max(1, int(max_files))
    if len(files) > limit:
        warnings.append(f"共发现 {len(files)} 个轨迹文件，本次只读取前 {limit} 个。")
        files = files[:limit]
    return files, warnings


def display_name_for_file(path: Path, folder: Path) -> str:
    """生成稳定且能区分同名文件的相对显示名称。"""
    try:
        relative = path.relative_to(folder)
    except ValueError:
        relative = Path(path.name)
    return f"文件夹/{relative.as_posix()}"
