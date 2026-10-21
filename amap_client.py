# -*- coding: utf-8 -*-
"""高德 Web 服务 API 封装（仅使用标准库 urllib）。

涉及接口：
- 地理编码（地址 -> GCJ-02 坐标）
- 路径规划（驾车 v3 / 步行 v3 / 骑行 v4）
"""
import json
import urllib.parse
import urllib.request

GEOCODE_URL = "https://restapi.amap.com/v3/geocode/geo"
REGEO_URL = "https://restapi.amap.com/v3/geocode/regeo"
TRANSIT_URL = "https://restapi.amap.com/v3/direction/transit"
DIRECTION_URLS = {
    "driving": "https://restapi.amap.com/v3/direction/driving",
    "walking": "https://restapi.amap.com/v3/direction/walking",
    "riding": "https://restapi.amap.com/v4/direction/bicycling",
}
MODE_LABELS = {"driving": "驾车", "walking": "步行", "riding": "骑行", "transit": "公交"}

# 驾车路径规划 strategy 参数（高德 v3 driving）
STRATEGY_LABELS = {
    "0": "最快捷（速度优先）",
    "1": "少收费（费用优先）",
    "2": "最短距离",
    "4": "躲避拥堵",
    "6": "不走高速",
}


class AmapError(RuntimeError):
    pass


# 高德错误码 -> 友好中文
ERROR_ZH = {
    "10001": "Key 不正确或已过期，请检查设置里的高德 Key",
    "10002": "当前 Key 没有该接口的使用权限",
    "10003": "今日调用量已达上限，请稍后再试",
    "10009": "Key 与服务平台不匹配（请确认申请的是「Web 服务」类型）",
    "10012": "当前 Key 没有该接口的使用权限",
    "20000": "请求参数不合法",
    "20800": "起终点不在中国境内，无法规划",
    "20801": "起终点附近搜不到路，请检查输入",
    "20802": "路线计算失败，请换一组起终点再试",
    "20803": "起终点距离过长，超出该出行方式上限（步行约100公里、骑行约500公里），请改用驾车",
}

# 高德英文错误信息关键词 -> 友好中文
ERROR_KEYWORD_ZH = {
    "INVALID_USER_KEY": "Key 不正确或已过期，请检查设置里的高德 Key",
    "INSUFFICIENT_PRIVILEGES": "当前 Key 没有该接口的使用权限（通常需企业认证或单独开通）",
    "NO_ROADS_NEARBY": "起终点附近搜不到路，请检查输入",
    "USER_DAILY_QUERY_OVER_LIMIT": "今日调用量已达上限，请稍后再试",
}


def friendly_error(info, code=""):
    """把高德错误码/信息转成友好中文提示，无法识别则原样返回。"""
    code = str(code or "")
    if code in ERROR_ZH:
        return ERROR_ZH[code]
    upper = str(info or "").upper()
    for key, msg in ERROR_KEYWORD_ZH.items():
        if key in upper:
            return msg
    return str(info or "未知错误")


def _http_get_json(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise AmapError("请求高德接口失败 HTTP %s" % e.code)
    except urllib.error.URLError as e:
        raise AmapError("无法连接高德服务器，请检查网络：%s" % e.reason)


def geocode(key, address):
    """地址 -> (lng, lat, formatted_address)，坐标为 GCJ-02。"""
    url = GEOCODE_URL + "?" + urllib.parse.urlencode({"key": key, "address": address})
    data = _http_get_json(url)
    if data.get("status") != "1":
        info = data.get("info") or "未知错误"
        code = str(data.get("infocode") or "")
        raise AmapError("地理编码失败：%s" % friendly_error(info, code))
    if not data.get("geocodes"):
        raise AmapError("地理编码失败：未找到该地址")
    g = data["geocodes"][0]
    loc = str(g.get("location", "")).split(",")
    if len(loc) != 2:
        raise AmapError("地理编码结果异常")
    return float(loc[0]), float(loc[1]), g.get("formatted_address") or address


def regeo(key, lng, lat):
    """逆地理编码，返回 (city_label, adcode)。"""
    url = REGEO_URL + "?" + urllib.parse.urlencode({
        "key": key, "location": "%.6f,%.6f" % (lng, lat)})
    data = _http_get_json(url)
    if data.get("status") != "1":
        info = data.get("info") or "未知错误"
        code = str(data.get("infocode") or "")
        raise AmapError("逆地理编码失败：%s" % friendly_error(info, code))
    ac = (data.get("regeocode") or {}).get("addressComponent") or {}
    province = ac.get("province") or ""
    city = ac.get("city") or ""
    adcode = ac.get("adcode") or ""
    label = city or province or adcode
    return label, adcode


def direction(key, mode, origin_gcj, dest_gcj, strategy="0", waypoints=None):
    """路径规划。

    origin_gcj / dest_gcj 为 (lng, lat) GCJ-02 元组。
    strategy 仅对驾车生效（见 STRATEGY_LABELS）。
    waypoints 仅对驾车生效，格式 "lng,lat;lng,lat"（GCJ-02）。
    返回 dict：
        distance_m: 总距离（米）
        duration_s: 预计耗时（秒）
        steps: 分段导航指令列表（polyline 为 GCJ-02 坐标 [[lng,lat],...]）
        origin / destination: 高德返回的坐标字符串（GCJ-02）
    """
    if mode not in DIRECTION_URLS:
        raise AmapError("不支持的出行方式：%s" % mode)
    origin = "%.6f,%.6f" % (origin_gcj[0], origin_gcj[1])
    destination = "%.6f,%.6f" % (dest_gcj[0], dest_gcj[1])
    params = {"key": key, "origin": origin, "destination": destination}
    if mode == "driving":
        params["strategy"] = strategy or "0"
        params["extensions"] = "all"
        if waypoints:
            params["waypoints"] = waypoints
    url = DIRECTION_URLS[mode] + "?" + urllib.parse.urlencode(params)
    data = _http_get_json(url)
    return _parse_direction(data, mode)


def _parse_direction(data, mode):
    # v4 骑行：errcode/errmsg/data（部分版本包 data.route，部分直接 data.paths）
    # v3 驾车/步行：status/info/route
    err = None
    code = ""
    if "errcode" in data:
        if data.get("errcode") not in (0, "0"):
            err = data.get("errmsg") or "未知错误"
            code = str(data.get("errcode") or "")
        d = data.get("data") or {}
        route = d.get("route") or d
    else:
        if data.get("status") != "1":
            err = data.get("info") or "未知错误"
            code = str(data.get("infocode") or "")
        route = data.get("route") or {}
    if err:
        raise AmapError("路径规划失败：%s" % friendly_error(err, code))

    paths = route.get("paths") or []
    if not paths:
        raise AmapError("未找到可行路线，请检查起终点")
    path = paths[0]

    steps = []
    for s in path.get("steps") or []:
        tmcs = []
        for t in s.get("tmcs") or []:
            tmcs.append({
                "status": _to_int(t.get("status")),
                "distance_m": _to_int(t.get("distance")),
                "polyline": _parse_polyline(t.get("polyline", "")),
            })
        steps.append({
            "instruction": s.get("instruction", ""),
            "road": s.get("road", ""),
            "action": s.get("action", ""),
            "orientation": s.get("orientation", ""),
            "distance_m": _to_int(s.get("distance")),
            "duration_s": _to_int(s.get("duration")),
            "polyline": _parse_polyline(s.get("polyline", "")),
            "tmcs": tmcs,
        })

    return {
        "distance_m": _to_int(path.get("distance")),
        "duration_s": _to_int(path.get("duration")),
        "steps": steps,
        "origin": route.get("origin", ""),
        "destination": route.get("destination", ""),
    }


def _to_int(v):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return 0


def _parse_polyline(poly):
    """'lng,lat;lng,lat;...' -> [[lng,lat], ...]"""
    pts = []
    if not poly:
        return pts
    for chunk in str(poly).split(";"):
        chunk = chunk.strip()
        if not chunk:
            continue
        try:
            lng, lat = chunk.split(",")
            pts.append([float(lng), float(lat)])
        except ValueError:
            continue
    return pts


def transit(key, origin_gcj, dest_gcj, city):
    """公交/地铁路径规划。city 为城市名或 adcode。"""
    origin = "%.6f,%.6f" % (origin_gcj[0], origin_gcj[1])
    destination = "%.6f,%.6f" % (dest_gcj[0], dest_gcj[1])
    params = {"key": key, "origin": origin, "destination": destination, "city": city}
    url = TRANSIT_URL + "?" + urllib.parse.urlencode(params)
    data = _http_get_json(url)
    return _parse_transit(data)


def _parse_transit(data):
    if data.get("status") != "1":
        info = data.get("info") or "未知错误"
        code = str(data.get("infocode") or "")
        raise AmapError("公交路径规划失败：%s" % friendly_error(info, code))
    route = data.get("route") or {}
    transits = route.get("transits") or []
    if not transits:
        raise AmapError("未找到公交换乘方案")
    t = transits[0]
    segments = []
    for seg in t.get("segments") or []:
        if "walking" in seg:
            w = seg["walking"] or {}
            poly = []
            for st in (w.get("steps") or []):
                poly.extend(_parse_polyline(st.get("polyline", "")))
            segments.append({
                "type": "步行", "name": "步行",
                "start": w.get("origin", ""), "end": w.get("destination", ""),
                "distance_m": _to_int(w.get("distance")),
                "duration_s": _to_int(w.get("duration")),
                "polyline": poly,
            })
        elif "bus" in seg:
            b = seg["bus"] or {}
            bl = (b.get("buslines") or [{}])[0] or {}
            seg_type = "地铁" if ("地铁" in (bl.get("type") or "")) else "公交"
            segments.append({
                "type": seg_type, "name": bl.get("name", ""),
                "start": (bl.get("departure_stop") or {}).get("name", ""),
                "end": (bl.get("arrival_stop") or {}).get("name", ""),
                "distance_m": _to_int(bl.get("distance")),
                "duration_s": _to_int(bl.get("duration")),
                "polyline": _parse_polyline(bl.get("polyline", "")),
            })
        elif "railway" in seg:
            rw = seg["railway"] or {}
            segments.append({
                "type": "铁路", "name": rw.get("trip", ""),
                "start": (rw.get("departure_stop") or {}).get("name", ""),
                "end": (rw.get("arrival_stop") or {}).get("name", ""),
                "distance_m": _to_int(rw.get("distance")),
                "duration_s": _to_int(rw.get("duration")),
                "polyline": [],
            })
        elif "entrance" in seg:
            e = seg["entrance"] or {}
            segments.append({"type": "进站", "name": e.get("name", ""), "start": "",
                             "end": "", "distance_m": 0, "duration_s": 0, "polyline": []})
        elif "exit" in seg:
            e = seg["exit"] or {}
            segments.append({"type": "出站", "name": e.get("name", ""), "start": "",
                             "end": "", "distance_m": 0, "duration_s": 0, "polyline": []})
    return {
        "distance_m": _to_int(t.get("distance")),
        "duration_s": _to_int(t.get("duration")),
        "cost": t.get("cost", ""),
        "walking_distance_m": _to_int(t.get("walking_distance")),
        "segments": segments,
    }
