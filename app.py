# -*- coding: utf-8 -*-
"""高德路径搜索与下载工具 —— 本地网页应用后端。

仅用 Python 标准库实现（http.server + urllib + json + csv + io 等）。
Excel(.xlsx) 批量导入依赖 openpyxl（见 requirements.txt，缺少时提示安装，
也可以直接用 .csv 导入）。

启动方式：python app.py  ，然后浏览器打开 http://127.0.0.1:8000
"""
import csv
import io
import json
import os
import random
import re
import shutil
import time
import uuid
import urllib.parse
import urllib.request
import webbrowser
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import amap_client
import storage
from coord import parse_coord, wgs84_to_gcj02, gcj02_to_wgs84
from paths import app_base_dir, resource_dir

BASE_DIR = app_base_dir()
STATIC_DIR = os.path.join(resource_dir(), "static")
TILES_DIR = os.path.join(BASE_DIR, "tiles")
PORT = 8000

TILE_URL_TEMPLATE = ("https://webrd0{s}.is.autonavi.com/appmaptile"
                     "?lang=zh_cn&size=1&scale=1&style=8&x={x}&y={y}&z={z}")

MIME = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
}


# ===================== 核心业务 =====================

def resolve_point(key, text):
    """把输入文本解析为一个坐标点信息。

    输入可以是地址（走地理编码）或经纬度（默认 WGS84，转 GCJ-02）。
    返回 dict：input / name / lng / lat（GCJ-02）/ lng_wgs / lat_wgs。
    """
    coord = parse_coord(text)
    if coord is not None:
        lng_wgs, lat_wgs = coord
        lng_gcj, lat_gcj = wgs84_to_gcj02(lng_wgs, lat_wgs)
        return {
            "input": text.strip(),
            "name": "%.6f,%.6f" % (lng_wgs, lat_wgs),
            "lng": lng_gcj,
            "lat": lat_gcj,
            "lng_wgs": lng_wgs,
            "lat_wgs": lat_wgs,
        }
    lng_gcj, lat_gcj, name = amap_client.geocode(key, text.strip())
    lng_wgs, lat_wgs = gcj02_to_wgs84(lng_gcj, lat_gcj)
    return {
        "input": text.strip(),
        "name": name,
        "lng": lng_gcj,
        "lat": lat_gcj,
        "lng_wgs": lng_wgs,
        "lat_wgs": lat_wgs,
    }


def _search_transit(key, o, d):
    """公交/地铁换乘：逆地理编码取城市，再调 transit，返回统一 route 对象。"""
    label, adcode = amap_client.regeo(key, o["lng"], o["lat"])
    r = amap_client.transit(key, (o["lng"], o["lat"]), (d["lng"], d["lat"]), label or adcode)
    segments = []
    full_gcj = []
    full_wgs = []
    for seg in r["segments"]:
        poly_gcj = seg["polyline"]
        poly_wgs = [list(gcj02_to_wgs84(lng, lat)) for lng, lat in poly_gcj]
        segments.append({
            "type": seg["type"], "name": seg["name"],
            "start": seg["start"], "end": seg["end"],
            "distance_m": seg["distance_m"], "duration_s": seg["duration_s"],
            "polyline_gcj": poly_gcj, "polyline_wgs": poly_wgs,
        })
        full_gcj.extend(poly_gcj)
        full_wgs.extend(poly_wgs)
    return {
        "mode": "transit", "mode_label": amap_client.MODE_LABELS["transit"],
        "origin": o, "destination": d, "waypoints": [],
        "distance_m": r["distance_m"], "duration_s": r["duration_s"],
        "cost": r["cost"],
        "segments": segments, "steps": [],
        "polyline_gcj": full_gcj, "polyline_wgs": full_wgs,
        "traffic_gcj": [], "traffic_wgs": [],
    }


def search_route(key, origin_text, dest_text, mode, strategy="0", waypoints=None):
    """搜索一条路线，返回统一结构的 route 对象（同时含 GCJ-02 与 WGS84）。

    waypoints：途经点文本列表（地址或 WGS84 经纬度），仅驾车有效。
    """
    o = resolve_point(key, origin_text)
    d = resolve_point(key, dest_text)
    if abs(o["lng"] - d["lng"]) < 1e-9 and abs(o["lat"] - d["lat"]) < 1e-9:
        raise ValueError("起点和终点相同，请检查输入")
    if mode == "transit":
        return _search_transit(key, o, d)
    wp_points = []
    for w in (waypoints or []):
        w = (w or "").strip()
        if w:
            wp_points.append(resolve_point(key, w))
    wp_str = ";".join("%.6f,%.6f" % (p["lng"], p["lat"]) for p in wp_points) or None
    r = amap_client.direction(key, mode, (o["lng"], o["lat"]), (d["lng"], d["lat"]),
                              strategy=strategy, waypoints=wp_str)

    steps = []
    full_gcj = []
    full_wgs = []
    traffic_gcj = []
    traffic_wgs = []
    for i, s in enumerate(r["steps"]):
        poly_gcj = s["polyline"]
        poly_wgs = [list(gcj02_to_wgs84(lng, lat)) for lng, lat in poly_gcj]
        steps.append({
            "index": i + 1,
            "instruction": s["instruction"],
            "road": s["road"],
            "action": s["action"],
            "orientation": s["orientation"],
            "distance_m": s["distance_m"],
            "duration_s": s["duration_s"],
            "polyline_gcj": poly_gcj,
            "polyline_wgs": poly_wgs,
        })
        full_gcj.extend(poly_gcj)
        full_wgs.extend(poly_wgs)
        for t in s.get("tmcs", []):
            t_gcj = t["polyline"]
            t_wgs = [list(gcj02_to_wgs84(lng, lat)) for lng, lat in t_gcj]
            traffic_gcj.append({"status": t["status"], "polyline_gcj": t_gcj})
            traffic_wgs.append({"status": t["status"], "polyline_wgs": t_wgs})

    return {
        "mode": mode,
        "mode_label": amap_client.MODE_LABELS.get(mode, mode),
        "origin": o,
        "destination": d,
        "waypoints": wp_points,
        "distance_m": r["distance_m"],
        "duration_s": r["duration_s"],
        "steps": steps,
        "polyline_gcj": full_gcj,
        "polyline_wgs": full_wgs,
        "traffic_gcj": traffic_gcj,
        "traffic_wgs": traffic_wgs,
    }


def normalize_mode(s):
    s = (s or "").strip().lower()
    if s in ("驾车", "driving", "drive", "car", "汽车", "开车"):
        return "driving"
    if s in ("步行", "walking", "walk", "走路"):
        return "walking"
    if s in ("骑行", "riding", "ride", "bike", "bicycle", "自行车", "单车", "骑车", "电动", "电动车"):
        return "riding"
    if s in ("公交", "地铁", "transit", "bus", "公交车", "公车"):
        return "transit"
    return ""


# ===================== 导入 =====================

def parse_xlsx(body):
    try:
        import openpyxl
    except ImportError:
        raise ValueError("缺少 openpyxl 库，无法读取 .xlsx。请在命令行运行：pip install openpyxl；或改用 .csv 文件导入。")
    wb = openpyxl.load_workbook(io.BytesIO(body), read_only=True, data_only=True)
    ws = wb.active
    rows = []
    for row in ws.iter_rows(values_only=True):
        if all(c is None or str(c).strip() == "" for c in row):
            continue
        rows.append([("" if c is None else str(c).strip()) for c in row])
    wb.close()
    return rows


def interpret_rows(rows):
    """把导入表格解析为 [{origin, destination, mode, name}]。"""
    items = []
    start = 0
    if rows and rows[0] and str(rows[0][0]).strip().lower() in ("起点", "origin", "start", "出发", "出发地"):
        start = 1
    for r in rows[start:]:
        origin = r[0] if len(r) > 0 else ""
        dest = r[1] if len(r) > 1 else ""
        mode = r[2] if len(r) > 2 else ""
        name = r[3] if len(r) > 3 else ""
        if not origin and not dest:
            continue
        items.append({"origin": origin, "destination": dest,
                      "mode": normalize_mode(mode), "name": name})
    return items


# ===================== 导出 =====================

def csv_to_bytes(rows):
    buf = io.StringIO()
    csv.writer(buf, lineterminator="\r\n").writerows(rows)
    return buf.getvalue().encode("utf-8-sig")  # utf-8-sig 让 Excel 正确识别中文


def save_download(fname, data):
    storage.ensure_download_dir()
    safe = re.sub(r'[\\/:*?"<>|]+', "_", fname)
    path = os.path.join(storage.DOWNLOAD_DIR, safe)
    with open(path, "wb") as f:
        f.write(data)
    return safe


def build_route_csv_rows(route):
    rows = [["序号", "导航指令", "道路名称", "动作", "方向", "距离(米)", "耗时(秒)", "累计距离(米)"]]
    cum = 0
    for s in route.get("steps", []):
        cum += s.get("distance_m", 0)
        rows.append([s.get("index"), s.get("instruction"), s.get("road"),
                     s.get("action"), s.get("orientation"),
                     s.get("distance_m"), s.get("duration_s"), cum])
    return rows


def build_stats_rows(routes):
    rows = [["序号", "备注", "起点", "终点", "出行方式", "距离(公里)", "预计耗时(分钟)"]]
    total = 0.0
    for i, r in enumerate(routes):
        km = r.get("distance_m", 0) / 1000.0
        total += km
        rows.append([i + 1, r.get("name", ""), r["origin"]["name"],
                     r["destination"]["name"], r.get("mode_label", ""),
                     "%.3f" % km, "%.1f" % (r.get("duration_s", 0) / 60.0)])
    rows.append(["", "", "", "", "合计", "%.3f" % total, ""])
    return rows


def build_batch_csv_rows(routes):
    rows = [["路线编号", "备注", "起点", "终点", "出行方式", "序号",
             "导航指令", "道路名称", "动作", "方向", "距离(米)", "耗时(秒)"]]
    for i, r in enumerate(routes):
        for s in r.get("steps", []):
            rows.append([i + 1, r.get("name", ""), r["origin"]["name"],
                         r["destination"]["name"], r.get("mode_label", ""),
                         s.get("index"), s.get("instruction"), s.get("road"),
                         s.get("action"), s.get("orientation"),
                         s.get("distance_m"), s.get("duration_s")])
    return rows


def route_feature(r):
    return {
        "type": "Feature",
        "properties": {
            "name": r.get("name", ""),
            "origin": r["origin"]["name"],
            "destination": r["destination"]["name"],
            "waypoints": [w.get("name", "") for w in r.get("waypoints", [])],
            "mode": r.get("mode"),
            "mode_label": r.get("mode_label", ""),
            "distance_m": r.get("distance_m", 0),
            "duration_s": r.get("duration_s", 0),
        },
        "geometry": {"type": "LineString", "coordinates": r.get("polyline_wgs", [])},
    }


def do_export(body):
    kind = body.get("kind")
    route = body.get("route")
    routes = body.get("routes")
    if not routes and route:
        routes = [route]
    routes = routes or []
    ts = time.strftime("%Y%m%d_%H%M%S")

    if kind == "route_csv":
        if not routes:
            raise ValueError("没有可导出的路线")
        data = csv_to_bytes(build_route_csv_rows(routes[0]))
        fname = "路线分段_%s.csv" % ts
    elif kind == "route_geojson":
        if not routes:
            raise ValueError("没有可导出的路线")
        fc = {"type": "FeatureCollection", "features": [route_feature(routes[0])]}
        data = json.dumps(fc, ensure_ascii=False).encode("utf-8")
        fname = "路线_WGS84_%s.geojson" % ts
    elif kind == "stats_csv":
        data = csv_to_bytes(build_stats_rows(routes))
        fname = "里程统计_%s.csv" % ts
    elif kind == "batch_geojson":
        fc = {"type": "FeatureCollection", "features": [route_feature(r) for r in routes]}
        data = json.dumps(fc, ensure_ascii=False).encode("utf-8")
        fname = "全部路线_WGS84_%s.geojson" % ts
    elif kind == "batch_csv":
        data = csv_to_bytes(build_batch_csv_rows(routes))
        fname = "全部路线分段_%s.csv" % ts
    elif kind == "trajectory_geojson":
        points = body.get("points") or []
        fc = {"type": "FeatureCollection", "features": [{
            "type": "Feature",
            "properties": {"name": "轨迹", "points_count": len(points)},
            "geometry": {"type": "LineString", "coordinates": points},
        }]}
        data = json.dumps(fc, ensure_ascii=False).encode("utf-8")
        fname = "轨迹_WGS84_%s.geojson" % ts
    elif kind == "trajectory_csv":
        points = body.get("points") or []
        rows = [["序号", "经度(WGS84)", "纬度(WGS84)"]]
        for i, p in enumerate(points):
            rows.append([i + 1, p[0], p[1]])
        data = csv_to_bytes(rows)
        fname = "轨迹_%s.csv" % ts
    else:
        raise ValueError("未知导出类型")

    filename = save_download(fname, data)
    return {"filename": filename, "url": "/downloads/" + urllib.parse.quote(filename)}


# ===================== 备份 / 恢复 =====================

def backup_to_zip():
    """把 data/ 与 downloads/ 打包为 zip 字节。"""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for d, arc in ((storage.DATA_DIR, "data"), (storage.DOWNLOAD_DIR, "downloads")):
            if os.path.isdir(d):
                for root, _dirs, files in os.walk(d):
                    for f in files:
                        full = os.path.join(root, f)
                        z.write(full, os.path.join(arc, os.path.relpath(full, d)))
    return buf.getvalue()


def restore_from_zip(data):
    """从 zip 字节恢复 data/ 与 downloads/，恢复前把当前数据备份到 backups/。"""
    ts = time.strftime("%Y%m%d_%H%M%S")
    parent = os.path.dirname(storage.DATA_DIR)
    backup_root = os.path.join(parent, "backups", "pre-restore-" + ts)
    os.makedirs(backup_root, exist_ok=True)
    for src, name in ((storage.DATA_DIR, "data"), (storage.DOWNLOAD_DIR, "downloads")):
        if os.path.isdir(src):
            shutil.copytree(src, os.path.join(backup_root, name))
    tmp = os.path.join(parent, "restore_tmp_" + uuid.uuid4().hex[:8])
    os.makedirs(tmp, exist_ok=True)
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            z.extractall(tmp)
        for name, dst_dir in (("data", storage.DATA_DIR), ("downloads", storage.DOWNLOAD_DIR)):
            src_dir = os.path.join(tmp, name)
            if os.path.isdir(src_dir):
                os.makedirs(dst_dir, exist_ok=True)
                for f in os.listdir(src_dir):
                    s = os.path.join(src_dir, f)
                    if os.path.isfile(s):
                        shutil.copy2(s, os.path.join(dst_dir, f))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return backup_root


# ===================== 瓦片缓存（离线地图） =====================

def get_tile(z, x, y):
    """获取高德瓦片字节：命中本地缓存直接返回，否则联网抓取并缓存到 tiles/。"""
    try:
        z, x, y = int(z), int(x), int(y)
    except (TypeError, ValueError):
        return None
    if not (0 <= z <= 22):
        return None
    cache = os.path.join(TILES_DIR, str(z), str(x), "%s.png" % y)
    if os.path.isfile(cache):
        with open(cache, "rb") as f:
            return f.read()
    s = random.choice(("1", "2", "3", "4"))
    url = TILE_URL_TEMPLATE.format(s=s, x=x, y=y, z=z)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = resp.read()
    except Exception:
        return None
    os.makedirs(os.path.dirname(cache), exist_ok=True)
    tmp = cache + ".tmp"
    with open(tmp, "wb") as f:
        f.write(data)
    os.replace(tmp, cache)
    return data


# ===================== HTTP 服务 =====================

class Handler(BaseHTTPRequestHandler):
    server_version = "RouteTool/1.0"

    def log_message(self, fmt, *args):
        print("[%s] %s" % (time.strftime("%H:%M:%S"), fmt % args))

    # ---- 响应工具 ----
    def _send_json(self, obj, status=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_error(self, msg, status=400):
        self._send_json({"success": False, "error": str(msg)}, status)

    def _send_file(self, path, download_name=None):
        try:
            with open(path, "rb") as f:
                data = f.read()
        except OSError:
            self._send_error("文件不存在", 404)
            return
        ext = os.path.splitext(path)[1].lower()
        self.send_response(200)
        self.send_header("Content-Type", MIME.get(ext, "application/octet-stream"))
        if download_name:
            quoted = urllib.parse.quote(download_name)
            self.send_header("Content-Disposition",
                             "attachment; filename*=UTF-8''%s" % quoted)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0) or 0)
        return self.rfile.read(length) if length else b""

    def _read_json(self):
        try:
            return json.loads(self._read_body().decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise ValueError("请求体不是有效的 JSON")

    def _static_path(self, rel):
        # 防目录穿越
        full = os.path.normpath(os.path.join(STATIC_DIR, rel))
        if not full.startswith(os.path.normpath(STATIC_DIR)):
            return None
        return full if os.path.isfile(full) else None

    # ---- GET ----
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/":
            p = self._static_path("index.html")
            if p:
                self._send_file(p)
            else:
                self._send_error("index.html 不存在", 500)
            return

        if path.startswith("/tiles/"):
            parts = path[len("/tiles/"):].strip("/").split("/")
            if len(parts) == 3:
                z, x, yp = parts[0], parts[1], parts[2]
                y = yp.rsplit(".", 1)[0]
                data = get_tile(z, x, y)
                if data:
                    self.send_response(200)
                    self.send_header("Content-Type", "image/png")
                    self.send_header("Content-Length", str(len(data)))
                    self.send_header("Cache-Control", "max-age=86400")
                    self.end_headers()
                    self.wfile.write(data)
                    return
            self._send_error("瓦片不存在", 404)
            return

        if path.startswith("/static/"):
            p = self._static_path(path[len("/static/"):])
            if p:
                self._send_file(p)
            else:
                self._send_error("静态资源不存在", 404)
            return

        if path.startswith("/downloads/"):
            name = urllib.parse.unquote(path[len("/downloads/"):])
            full = os.path.normpath(os.path.join(storage.DOWNLOAD_DIR, name))
            if full.startswith(os.path.normpath(storage.DOWNLOAD_DIR)) and os.path.isfile(full):
                self._send_file(full, download_name=os.path.basename(name))
            else:
                self._send_error("文件不存在", 404)
            return

        if path == "/api/config":
            self._send_json({"success": True, "key": storage.get_key()})
            return
        if path == "/api/plan":
            self._send_json({"success": True, "plan": storage.get_plan()})
            return
        if path == "/api/history":
            self._send_json({"success": True, "history": storage.get_history()})
            return
        if path == "/api/backup":
            data = backup_to_zip()
            fname = "高德路线工具备份_%s.zip" % time.strftime("%Y%m%d_%H%M%S")
            self.send_response(200)
            self.send_header("Content-Type", "application/zip")
            self.send_header("Content-Disposition",
                             "attachment; filename*=UTF-8''%s" % urllib.parse.quote(fname))
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return

        self._send_error("未知接口", 404)

    # ---- POST ----
    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        try:
            if path == "/api/config":
                body = self._read_json()
                key = storage.set_key(body.get("key", ""))
                self._send_json({"success": True, "key": key})
            elif path == "/api/search":
                body = self._read_json()
                key = storage.get_key()
                if not key:
                    self._send_error("请先在“设置”里填写高德 Key", 400)
                    return
                route = search_route(key, body.get("origin", ""),
                                     body.get("destination", ""), body.get("mode", "driving"),
                                     strategy=str(body.get("strategy", "0")),
                                     waypoints=body.get("waypoints"))
                # 自动写入搜索历史
                entry = {
                    "id": uuid.uuid4().hex[:8],
                    "ts": time.time(),
                    "origin_text": body.get("origin", ""),
                    "dest_text": body.get("destination", ""),
                    "mode": route["mode"],
                    "mode_label": route["mode_label"],
                    "distance_m": route["distance_m"],
                    "duration_s": route["duration_s"],
                    "route": route,
                }
                storage.add_history(entry)
                self._send_json({"success": True, "route": route})
            elif path == "/api/convert":
                body = self._read_json()
                lng = float(body.get("lng"))
                lat = float(body.get("lat"))
                direction = body.get("direction", "wgs2gcj")
                if direction == "wgs2gcj":
                    out_lng, out_lat = wgs84_to_gcj02(lng, lat)
                    label = "WGS84 -> GCJ-02"
                elif direction == "gcj2wgs":
                    out_lng, out_lat = gcj02_to_wgs84(lng, lat)
                    label = "GCJ-02 -> WGS84"
                else:
                    raise ValueError("未知转换方向")
                self._send_json({
                    "success": True,
                    "label": label,
                    "input": {"lng": lng, "lat": lat},
                    "output": {"lng": round(out_lng, 6), "lat": round(out_lat, 6)},
                })
            elif path == "/api/import":
                raw = self._read_body()
                filename = self.headers.get("X-Filename", "")
                items = interpret_rows(self._parse_import(raw, filename))
                self._send_json({"success": True, "items": items, "count": len(items)})
            elif path == "/api/batch":
                body = self._read_json()
                key = storage.get_key()
                if not key:
                    self._send_error("请先在“设置”里填写高德 Key", 400)
                    return
                items = body.get("items", [])
                default_mode = body.get("default_mode", "driving")
                strategy = str(body.get("strategy", "0"))
                results = []
                for it in items:
                    mode = it.get("mode") or default_mode
                    try:
                        route = search_route(key, it.get("origin", ""),
                                             it.get("destination", ""), mode, strategy=strategy)
                        route["name"] = it.get("name", "")
                        results.append({"ok": True, "name": it.get("name", ""),
                                        "route": route})
                    except Exception as e:
                        results.append({"ok": False, "name": it.get("name", ""),
                                        "origin": it.get("origin", ""),
                                        "destination": it.get("destination", ""),
                                        "error": str(e)})
                self._send_json({"success": True, "results": results,
                                 "total": len(results),
                                 "ok_count": sum(1 for r in results if r["ok"])})
            elif path == "/api/export":
                body = self._read_json()
                self._send_json({"success": True, **do_export(body)})
            elif path == "/api/plan":
                body = self._read_json()
                plan = storage.set_plan(body.get("plan", {"date": "", "items": []}))
                self._send_json({"success": True, "plan": plan})
            elif path == "/api/history/delete":
                body = self._read_json()
                self._send_json({"success": True,
                                 "history": storage.delete_history(int(body.get("index", -1)))})
            elif path == "/api/history/clear":
                self._send_json({"success": True, "history": storage.clear_history()})
            elif path == "/api/restore":
                raw = self._read_body()
                backup_root = restore_from_zip(raw)
                self._send_json({"success": True, "backup_root": backup_root})
            else:
                self._send_error("未知接口", 404)
        except ValueError as e:
            self._send_error(str(e), 400)
        except amap_client.AmapError as e:
            self._send_error(str(e), 400)
        except Exception as e:  # noqa: BLE001
            self._send_error("服务器内部错误：%s" % e, 500)

    def _parse_import(self, raw, filename):
        name = (filename or "").lower()
        if name.endswith(".csv") or not raw.startswith(b"PK"):
            text = raw.decode("utf-8-sig", errors="replace")
            return [r for r in csv.reader(io.StringIO(text)) if any(c.strip() for c in r)]
        return parse_xlsx(raw)


def main():
    os.makedirs(STATIC_DIR, exist_ok=True)
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    url = "http://127.0.0.1:%d" % PORT
    print("=" * 56)
    print("  高德路径搜索与下载工具 已启动")
    print("  请在浏览器打开： %s" % url)
    print("  关闭本窗口即停止服务（Ctrl+C 也可停止）")
    print("=" * 56)
    try:
        webbrowser.open(url)
    except Exception:
        pass
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止。")
        server.shutdown()


if __name__ == "__main__":
    main()
