# -*- coding: utf-8 -*-
"""GCJ-02（火星坐标）与 WGS84 坐标互转。

高德接口内部使用 GCJ-02；本工具对外统一输出 WGS84，
所以路线结果里的坐标都会在这里做一次转换。
"""
import math
import re

A = 6378245.0
EE = 0.00669342162296594323


def _out_of_china(lng, lat):
    """中国境外不转换（无偏移）。"""
    return not (72.004 <= lng <= 137.8347 and 0.8293 <= lat <= 55.8271)


def _transform_lat(x, y):
    ret = -100.0 + 2.0 * x + 3.0 * y + 0.2 * y * y + 0.1 * x * y + 0.2 * math.sqrt(abs(x))
    ret += (20.0 * math.sin(6.0 * x * math.pi) + 20.0 * math.sin(2.0 * x * math.pi)) * 2.0 / 3.0
    ret += (20.0 * math.sin(y * math.pi) + 40.0 * math.sin(y / 3.0 * math.pi)) * 2.0 / 3.0
    ret += (160.0 * math.sin(y / 12.0 * math.pi) + 320.0 * math.sin(y * math.pi / 30.0)) * 2.0 / 3.0
    return ret


def _transform_lng(x, y):
    ret = 300.0 + x + 2.0 * y + 0.1 * x * x + 0.1 * x * y + 0.1 * math.sqrt(abs(x))
    ret += (20.0 * math.sin(6.0 * x * math.pi) + 20.0 * math.sin(2.0 * x * math.pi)) * 2.0 / 3.0
    ret += (20.0 * math.sin(x * math.pi) + 40.0 * math.sin(x / 3.0 * math.pi)) * 2.0 / 3.0
    ret += (150.0 * math.sin(x / 12.0 * math.pi) + 300.0 * math.sin(x / 30.0 * math.pi)) * 2.0 / 3.0
    return ret


def wgs84_to_gcj02(lng, lat):
    """WGS84 -> GCJ-02，返回 (lng, lat)。"""
    if _out_of_china(lng, lat):
        return lng, lat
    dlat = _transform_lat(lng - 105.0, lat - 35.0)
    dlng = _transform_lng(lng - 105.0, lat - 35.0)
    radlat = lat / 180.0 * math.pi
    magic = math.sin(radlat)
    magic = 1 - EE * magic * magic
    sqrtmagic = math.sqrt(magic)
    dlat = (dlat * 180.0) / ((A * (1 - EE)) / (magic * sqrtmagic) * math.pi)
    dlng = (dlng * 180.0) / (A / sqrtmagic * math.cos(radlat) * math.pi)
    return lng + dlng, lat + dlat


def gcj02_to_wgs84(lng, lat):
    """GCJ-02 -> WGS84，返回 (lng, lat)。"""
    if _out_of_china(lng, lat):
        return lng, lat
    g_lng, g_lat = wgs84_to_gcj02(lng, lat)
    d_lng = g_lng - lng
    d_lat = g_lat - lat
    return lng - d_lng, lat - d_lat


def parse_coord(text):
    """把字符串解析为 (lng, lat) 浮点坐标；不是坐标则返回 None。

    支持 "lng,lat" / "lng lat"（中英文逗号、空白分隔均可）。
    若明显写反（第一个是纬度、第二个是经度），自动纠正为 (lng, lat)。
    """
    if not text:
        return None
    t = str(text).strip()
    parts = [p for p in re.split(r"[，,\s]+", t) if p]
    if len(parts) != 2:
        return None
    try:
        a = float(parts[0])
        b = float(parts[1])
    except ValueError:
        return None
    # 约定顺序为 经度,纬度；中国范围经度约 72~138，纬度约 0~56
    if 72.0 <= a <= 138.0 and 0.0 <= b <= 56.0:
        return a, b
    if 72.0 <= b <= 138.0 and 0.0 <= a <= 56.0:
        return b, a
    return a, b
