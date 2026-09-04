"""iGPSPORT 与 Onelap/顽鹿 OTM 的本地数据下载连接器。"""

from __future__ import annotations

import base64
import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests


class PlatformError(RuntimeError):
    """平台登录、列表或下载失败时的可读异常。"""


@dataclass(frozen=True)
class RemoteActivity:
    platform: str
    activity_id: str
    title: str
    start_time: str = ""
    distance_km: float | None = None
    duration_s: int | None = None

    def label(self) -> str:
        parts = [self.start_time[:19] or "时间未知", self.title]
        if self.distance_km is not None and self.distance_km > 0:
            parts.append(f"{self.distance_km:.1f} km")
        return " · ".join(part for part in parts if part)

    def filename(self) -> str:
        stamp = re.sub(r"[^0-9]+", "-", self.start_time[:19]).strip("-") or "unknown-time"
        safe_id = re.sub(r"[^A-Za-z0-9_-]+", "-", self.activity_id).strip("-") or "activity"
        return f"{self.platform.lower()}-{stamp}-{safe_id}.fit"


def is_fit_file(data: bytes) -> bool:
    """FIT 头部第 8-11 字节应包含 .FIT。"""
    return len(data) >= 14 and data[8:12] == b".FIT"


def save_downloaded_activity(project_root: Path, activity: RemoteActivity, data: bytes) -> Path:
    """把平台文件安全地保存到项目 records/downloaded 下，避免覆盖不同内容。"""
    target_dir = project_root / "records" / "downloaded" / activity.platform.lower()
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / activity.filename()
    if target.exists():
        existing = target.read_bytes()
        if existing == data:
            return target
        digest = hashlib.sha256(data).hexdigest()[:8]
        target = target.with_name(f"{target.stem}-{digest}{target.suffix}")
    target.write_bytes(data)
    return target


class _PlatformClient:
    def __init__(self, session: requests.Session | None = None, timeout: tuple[int, int] = (15, 90)):
        self.session = session or requests.Session()
        self.timeout = timeout

    def _send(self, method: str, url: str, **kwargs):
        kwargs.setdefault("timeout", self.timeout)
        try:
            return self.session.request(method, url, **kwargs)
        except requests.RequestException as exc:
            raise PlatformError(f"无法连接运动平台：{exc}") from exc

    def _json(self, method: str, url: str, platform: str, **kwargs) -> dict[str, Any]:
        response = self._send(method, url, **kwargs)
        if response.status_code == 401:
            raise PlatformError(f"{platform} 登录已过期或账号验证失败。")
        if not 200 <= response.status_code < 300:
            raise PlatformError(f"{platform} 返回 HTTP {response.status_code}。")
        try:
            payload = response.json()
        except (ValueError, TypeError) as exc:
            raise PlatformError(f"{platform} 返回了无法识别的数据。") from exc
        if not isinstance(payload, dict):
            raise PlatformError(f"{platform} 返回的数据结构不正确。")
        return payload

    def _bytes(self, url: str, platform: str, **kwargs) -> bytes:
        response = self._send("GET", url, **kwargs)
        if not 200 <= response.status_code < 300:
            raise PlatformError(f"{platform} 文件下载返回 HTTP {response.status_code}。")
        data = bytes(response.content)
        if not is_fit_file(data):
            raise PlatformError(f"{platform} 返回的文件不是有效 FIT 文件。")
        return data


class IGPSportClient(_PlatformClient):
    PLATFORM = "iGPSPORT"
    BASE = "https://prod.zh.igpsport.com/service"
    LOGIN_URL = f"{BASE}/auth/account/login"
    ACTIVITY_URL = f"{BASE}/web-gateway/web-analyze/activity/queryMyActivity"
    DOWNLOAD_URL = f"{BASE}/web-gateway/web-analyze/activity/getDownloadUrl"

    @staticmethod
    def _headers(token: str) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {token.strip()}",
            "Accept": "application/json, text/plain, */*",
            "Origin": "https://app.igpsport.cn",
            "Referer": "https://app.igpsport.cn/",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) RideScope/1.0",
        }

    def login(self, username: str, password: str) -> str:
        payload = self._json(
            "POST",
            self.LOGIN_URL,
            self.PLATFORM,
            json={"username": username.strip(), "password": password, "appId": "igpsport-web"},
            headers={"Content-Type": "application/json"},
        )
        if payload.get("code") != 0:
            raise PlatformError(f"iGPSPORT 登录失败：{payload.get('message') or '账号、密码或验证方式不正确'}")
        data = payload.get("data") or {}
        token = data.get("access_token") if isinstance(data, dict) else None
        if not token:
            raise PlatformError("iGPSPORT 登录响应中没有访问令牌。")
        return str(token)

    def list_activities(self, token: str, limit: int = 10) -> list[RemoteActivity]:
        limit = max(1, min(int(limit), 1000))
        result: list[RemoteActivity] = []
        page = 1
        while len(result) < limit:
            payload = self._json(
                "GET",
                self.ACTIVITY_URL,
                self.PLATFORM,
                params={"pageNo": page, "pageSize": 20, "reqType": 0, "sort": 1},
                headers=self._headers(token),
            )
            if payload.get("code") != 0:
                raise PlatformError(f"iGPSPORT 活动列表读取失败：{payload.get('message') or '未知错误'}")
            data = payload.get("data") or {}
            rows = data.get("rows") or data.get("list") or [] if isinstance(data, dict) else []
            if not rows:
                break
            for item in rows:
                if not isinstance(item, dict):
                    continue
                ride_id = item.get("rideId") or item.get("RideId") or item.get("id")
                if ride_id is None:
                    continue
                start = str(item.get("startTime") or item.get("start_time") or "")
                title = str(item.get("title") or item.get("name") or item.get("activityName") or "骑行记录")
                distance = _distance_km(item)
                duration = _integer(item, "duration", "timeSeconds", "time_seconds", "totalTime")
                result.append(RemoteActivity(self.PLATFORM, str(ride_id), title, start, distance, duration))
                if len(result) >= limit:
                    break
            total_page = _integer(data, "totalPage") or 1
            if page >= total_page:
                break
            page += 1
        return result

    def download_activity(self, token: str, activity: RemoteActivity) -> bytes:
        payload = self._json(
            "GET",
            f"{self.DOWNLOAD_URL}/{quote(activity.activity_id, safe='')}",
            self.PLATFORM,
            headers=self._headers(token),
        )
        if payload.get("code") != 0:
            raise PlatformError(f"iGPSPORT 下载地址获取失败：{payload.get('message') or '未知错误'}")
        value = payload.get("data")
        if isinstance(value, dict):
            value = value.get("url") or value.get("downloadUrl") or value.get("fileUrl")
        if not isinstance(value, str) or not value.startswith("https://"):
            raise PlatformError("iGPSPORT 没有返回有效的 FIT 下载地址。")
        return self._bytes(value, self.PLATFORM, headers=self._headers(token))


class OnelapClient(_PlatformClient):
    PLATFORM = "Onelap"
    BASE = "https://otm.onelap.cn"
    LOGIN_URL = f"{BASE}/api/login"
    ACTIVITY_URL = f"{BASE}/api/otm/ride_record/list"

    @staticmethod
    def _headers(token: str | None = None) -> dict[str, str]:
        headers = {
            "Origin": OnelapClient.BASE,
            "Referer": f"{OnelapClient.BASE}/calendar",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) RideScope/1.0",
        }
        if token:
            headers["Authorization"] = token.strip()
        return headers

    def login(self, account: str, password: str) -> str:
        password_md5 = hashlib.md5(password.encode("utf-8"), usedforsecurity=False).hexdigest()
        payload = self._json(
            "POST",
            self.LOGIN_URL,
            self.PLATFORM,
            json={"account": account.strip(), "password": password_md5},
            headers=self._headers(),
        )
        if payload.get("code") != 200:
            raise PlatformError(f"Onelap 登录失败：{payload.get('error') or payload.get('message') or '账号或密码不正确'}")
        data = payload.get("data") or []
        if isinstance(data, dict):
            data = [data]
        token = next((item.get("token") for item in data if isinstance(item, dict) and item.get("token")), None)
        if not token:
            raise PlatformError("Onelap 登录响应中没有访问令牌。")
        return str(token)

    def list_activities(self, token: str, limit: int = 10) -> list[RemoteActivity]:
        limit = max(1, min(int(limit), 1000))
        result: list[RemoteActivity] = []
        page = 1
        while len(result) < limit:
            payload = self._json(
                "POST",
                self.ACTIVITY_URL,
                self.PLATFORM,
                json={"page": page, "limit": 20},
                headers=self._headers(token),
            )
            if payload.get("code") != 200:
                raise PlatformError(f"Onelap 活动列表读取失败：{payload.get('error') or payload.get('message') or '未知错误'}")
            data = payload.get("data") or {}
            rows = data.get("list") or [] if isinstance(data, dict) else []
            if not rows:
                break
            for item in rows:
                if not isinstance(item, dict) or item.get("id") is None:
                    continue
                start = str(item.get("start_riding_time") or "")
                title = str(item.get("name") or "").strip()
                if not title or title == "null":
                    title = f"{start[:10]} 骑行" if start else "骑行记录"
                distance = _number(item, "distance_km")
                duration = _integer(item, "time_seconds")
                result.append(RemoteActivity(self.PLATFORM, str(item["id"]), title, start, distance, duration))
                if len(result) >= limit:
                    break
            pagination = data.get("pagination") if isinstance(data, dict) else None
            has_more = bool(pagination.get("has_more")) if isinstance(pagination, dict) else len(rows) >= 20
            if not has_more:
                break
            page += 1
        return result

    def download_activity(self, token: str, activity: RemoteActivity) -> bytes:
        detail_url = f"{self.BASE}/api/otm/ride_record/analysis/{quote(activity.activity_id, safe='')}"
        payload = self._json("GET", detail_url, self.PLATFORM, headers=self._headers(token))
        if payload.get("code") != 200:
            raise PlatformError(f"Onelap 活动详情读取失败：{payload.get('error') or payload.get('message') or '未知错误'}")
        data = payload.get("data") or {}
        riding = data.get("ridingRecord") or {} if isinstance(data, dict) else {}
        durl = riding.get("durl") if isinstance(riding, dict) else None
        fit_url = riding.get("fitUrl") if isinstance(riding, dict) else None

        if isinstance(durl, str) and durl.startswith("https://"):
            try:
                return self._bytes(durl, self.PLATFORM, headers={"User-Agent": self._headers()["User-Agent"]})
            except PlatformError:
                pass

        if not isinstance(fit_url, str) or not fit_url:
            raise PlatformError("该 Onelap 记录没有可下载的 FIT 文件。")
        encoded = base64.b64encode(fit_url.encode("utf-8")).decode("ascii")
        fallback = f"{self.BASE}/api/otm/ride_record/analysis/fit_content/{quote(encoded, safe='')}"
        return self._bytes(fallback, self.PLATFORM, headers=self._headers(token))


def _number(mapping: dict[str, Any], *keys: str) -> float | None:
    for key in keys:
        value = mapping.get(key)
        try:
            if value is not None and value != "":
                return float(value)
        except (TypeError, ValueError):
            continue
    return None


def _integer(mapping: dict[str, Any], *keys: str) -> int | None:
    value = _number(mapping, *keys)
    return None if value is None else int(value)


def _distance_km(item: dict[str, Any]) -> float | None:
    direct = _number(item, "distanceKm", "distance_km")
    if direct is not None:
        return direct
    value = _number(item, "distance", "totalDistance")
    if value is None:
        return None
    return value / 1000.0 if value > 1000 else value
