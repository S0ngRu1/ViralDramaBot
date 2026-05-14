"""
位置名称 → 坐标 解析

视频号位置搜索接口走的是 GCJ-02 坐标系，所以无论用哪家服务，最终都需要 GCJ-02。

支持优先级：
1. 字符串里直接含坐标，如 "34.640136,113.593982" 或 "34.640136, 113.593982" → 视为 GCJ-02 直接返回；
2. 环境变量 TENCENT_MAP_KEY（腾讯地图，原生 GCJ-02）；
3. 环境变量 AMAP_KEY（高德，原生 GCJ-02）；
4. Nominatim（OpenStreetMap，免 key 但返回 WGS-84，需做坐标系转换）。

任一服务返回失败时回退到下一个，全部失败返回 None。
"""

from __future__ import annotations

import math
import os
import re
from typing import Optional, Tuple

import requests

from src.core.logger import logger


# (lat, lng) 元组，统一使用 GCJ-02
Coord = Tuple[float, float]

_GEOCODE_TIMEOUT = float(os.getenv("WEIXIN_GEOCODE_TIMEOUT", "6"))
_COORD_PATTERN = re.compile(
    r"^\s*(-?\d{1,3}(?:\.\d+)?)\s*[,，]\s*(-?\d{1,3}(?:\.\d+)?)\s*$"
)


# ---------- 坐标系转换：WGS-84 ↔ GCJ-02 ----------
# 参考：https://on4wp7.codeplex.com/SourceControl/changeset/view/21484#353936

_A = 6378245.0
_EE = 0.00669342162296594323


def _out_of_china(lng: float, lat: float) -> bool:
    return not (72.004 <= lng <= 137.8347 and 0.8293 <= lat <= 55.8271)


def _transform_lat(x: float, y: float) -> float:
    ret = -100.0 + 2.0 * x + 3.0 * y + 0.2 * y * y + 0.1 * x * y + 0.2 * math.sqrt(abs(x))
    ret += (20.0 * math.sin(6.0 * x * math.pi) + 20.0 * math.sin(2.0 * x * math.pi)) * 2.0 / 3.0
    ret += (20.0 * math.sin(y * math.pi) + 40.0 * math.sin(y / 3.0 * math.pi)) * 2.0 / 3.0
    ret += (160.0 * math.sin(y / 12.0 * math.pi) + 320.0 * math.sin(y * math.pi / 30.0)) * 2.0 / 3.0
    return ret


def _transform_lng(x: float, y: float) -> float:
    ret = 300.0 + x + 2.0 * y + 0.1 * x * x + 0.1 * x * y + 0.1 * math.sqrt(abs(x))
    ret += (20.0 * math.sin(6.0 * x * math.pi) + 20.0 * math.sin(2.0 * x * math.pi)) * 2.0 / 3.0
    ret += (20.0 * math.sin(x * math.pi) + 40.0 * math.sin(x / 3.0 * math.pi)) * 2.0 / 3.0
    ret += (150.0 * math.sin(x / 12.0 * math.pi) + 300.0 * math.sin(x / 30.0 * math.pi)) * 2.0 / 3.0
    return ret


def wgs84_to_gcj02(lng: float, lat: float) -> Tuple[float, float]:
    """WGS-84 (OSM/GPS) → GCJ-02 (腾讯/高德/微信)"""
    if _out_of_china(lng, lat):
        return lng, lat
    d_lat = _transform_lat(lng - 105.0, lat - 35.0)
    d_lng = _transform_lng(lng - 105.0, lat - 35.0)
    rad_lat = lat / 180.0 * math.pi
    magic = math.sin(rad_lat)
    magic = 1 - _EE * magic * magic
    sqrt_magic = math.sqrt(magic)
    d_lat = (d_lat * 180.0) / ((_A * (1 - _EE)) / (magic * sqrt_magic) * math.pi)
    d_lng = (d_lng * 180.0) / (_A / sqrt_magic * math.cos(rad_lat) * math.pi)
    return lng + d_lng, lat + d_lat


# ---------- 公开入口 ----------


def parse_coord_literal(text: str) -> Optional[Coord]:
    """允许直接输入 "lat,lng" 形式来指定坐标，跳过任何网络请求。"""
    if not text:
        return None
    m = _COORD_PATTERN.match(text)
    if not m:
        return None
    try:
        lat = float(m.group(1))
        lng = float(m.group(2))
    except ValueError:
        return None
    if -90 <= lat <= 90 and -180 <= lng <= 180:
        return lat, lng
    return None


def geocode(address: str) -> Optional[Coord]:
    """地理编码：地名字符串 → (lat, lng) GCJ-02。"""
    if not address:
        return None

    literal = parse_coord_literal(address)
    if literal:
        logger.info(f"地理编码：检测到坐标字面量 '{address}' → {literal}")
        return literal

    for fn in (_geocode_tencent, _geocode_amap, _geocode_nominatim):
        try:
            coord = fn(address)
            if coord:
                lat, lng = coord
                logger.info(f"地理编码：{fn.__name__} 解析 '{address}' → ({lat}, {lng})")
                return coord
        except Exception as e:
            logger.warning(f"地理编码：{fn.__name__} 失败: {e}")

    logger.warning(f"地理编码：所有后端都未能解析 '{address}'")
    return None


# ---------- 各家后端 ----------


def _geocode_tencent(address: str) -> Optional[Coord]:
    key = os.getenv("TENCENT_MAP_KEY") or os.getenv("WEIXIN_TENCENT_MAP_KEY")
    if not key:
        return None
    resp = requests.get(
        "https://apis.map.qq.com/ws/geocoder/v1/",
        params={"address": address, "key": key},
        timeout=_GEOCODE_TIMEOUT,
    )
    data = resp.json()
    if data.get("status") != 0:
        logger.warning(f"腾讯地理编码失败: {data.get('message')} (status={data.get('status')})")
        return None
    loc = (data.get("result") or {}).get("location") or {}
    lat = loc.get("lat")
    lng = loc.get("lng")
    if lat is None or lng is None:
        return None
    return float(lat), float(lng)


def _geocode_amap(address: str) -> Optional[Coord]:
    key = os.getenv("AMAP_KEY") or os.getenv("WEIXIN_AMAP_KEY")
    if not key:
        return None
    resp = requests.get(
        "https://restapi.amap.com/v3/geocode/geo",
        params={"address": address, "key": key},
        timeout=_GEOCODE_TIMEOUT,
    )
    data = resp.json()
    if str(data.get("status")) != "1":
        logger.warning(f"高德地理编码失败: {data.get('info')} (infocode={data.get('infocode')})")
        return None
    geocodes = data.get("geocodes") or []
    if not geocodes:
        return None
    loc = geocodes[0].get("location") or ""
    parts = loc.split(",")
    if len(parts) != 2:
        return None
    try:
        lng = float(parts[0])
        lat = float(parts[1])
    except ValueError:
        return None
    return lat, lng


def _geocode_nominatim(address: str) -> Optional[Coord]:
    """OSM Nominatim 免 key 接口，返回 WGS-84，需要转换为 GCJ-02。"""
    resp = requests.get(
        "https://nominatim.openstreetmap.org/search",
        params={"q": address, "format": "json", "limit": 1, "accept-language": "zh-CN"},
        headers={
            "User-Agent": "ViralDramaBot/1.0 (https://github.com/) location lookup",
        },
        timeout=_GEOCODE_TIMEOUT,
    )
    items = resp.json() or []
    if not items:
        return None
    item = items[0]
    try:
        wgs_lat = float(item["lat"])
        wgs_lng = float(item["lon"])
    except (KeyError, ValueError):
        return None
    gcj_lng, gcj_lat = wgs84_to_gcj02(wgs_lng, wgs_lat)
    return gcj_lat, gcj_lng
