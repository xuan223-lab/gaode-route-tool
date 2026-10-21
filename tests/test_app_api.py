# -*- coding: utf-8 -*-
"""HTTP 接口测试（mock 高德，不联网）。"""
import io
import json
import unittest
import zipfile
from unittest.mock import patch

import app
from helpers import TestServer

FAKE_DIRECTION = {
    "distance_m": 5000, "duration_s": 600,
    "steps": [
        {"instruction": "直行", "road": "某路", "action": "直行", "orientation": "东",
         "distance_m": 1000, "duration_s": 120, "polyline": [[116.4, 39.9], [116.45, 39.92]]},
    ],
    "origin": "116.4,39.9", "destination": "116.5,39.95",
}


def fake_geocode(key, address):
    # 不同地址返回不同坐标，避免起终点相同
    coords = {"北京": (116.4, 39.9), "上海": (116.5, 39.95),
              "a": (116.4, 39.9), "b": (116.5, 39.95),
              "c": (116.6, 40.0), "d": (116.7, 40.05)}
    lng, lat = coords.get(address, (116.4, 39.9))
    return lng, lat, address


class TestApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = TestServer()

    @classmethod
    def tearDownClass(cls):
        cls.srv.close()

    def test_config_roundtrip(self):
        status, data = self.srv.json("POST", "/api/config", {"key": "testkey"})
        self.assertEqual(status, 200)
        self.assertEqual(data["key"], "testkey")
        _, data = self.srv.json("GET", "/api/config")
        self.assertEqual(data["key"], "testkey")

    def test_convert(self):
        _, data = self.srv.json("POST", "/api/convert",
                                {"lng": 116.397428, "lat": 39.90923, "direction": "wgs2gcj"})
        self.assertTrue(data["success"])
        self.assertAlmostEqual(data["output"]["lng"], 116.403672, places=5)

    @patch.object(app.amap_client, "geocode", side_effect=fake_geocode)
    @patch.object(app.amap_client, "direction", return_value=FAKE_DIRECTION)
    def test_search_ok(self, mock_dir, mock_geo):
        self.srv.json("POST", "/api/config", {"key": "k"})
        status, data = self.srv.json("POST", "/api/search",
                                     {"origin": "北京", "destination": "上海", "mode": "driving"})
        self.assertEqual(status, 200)
        self.assertTrue(data["success"])
        self.assertEqual(data["route"]["distance_m"], 5000)
        self.assertEqual(data["route"]["mode_label"], "驾车")
        _, hist = self.srv.json("GET", "/api/history")
        self.assertEqual(len(hist["history"]), 1)

    def test_search_no_key(self):
        self.srv.json("POST", "/api/config", {"key": ""})
        status, data = self.srv.json("POST", "/api/search",
                                     {"origin": "a", "destination": "b", "mode": "driving"})
        self.assertEqual(status, 400)
        self.assertFalse(data["success"])

    def test_search_same_point(self):
        self.srv.json("POST", "/api/config", {"key": "k"})
        status, data = self.srv.json("POST", "/api/search",
                                     {"origin": "116.4,39.9", "destination": "116.4,39.9",
                                      "mode": "driving"})
        self.assertEqual(status, 400)
        self.assertIn("相同", data["error"])

    @patch.object(app.amap_client, "geocode", side_effect=fake_geocode)
    @patch.object(app.amap_client, "direction", return_value=FAKE_DIRECTION)
    def test_search_passes_strategy(self, mock_dir, mock_geo):
        self.srv.json("POST", "/api/config", {"key": "k"})
        _, data = self.srv.json("POST", "/api/search",
                                {"origin": "北京", "destination": "上海",
                                 "mode": "driving", "strategy": "6"})
        self.assertTrue(data["success"])
        self.assertEqual(mock_dir.call_args[1]["strategy"], "6")

    @patch.object(app.amap_client, "geocode", side_effect=fake_geocode)
    @patch.object(app.amap_client, "direction", return_value=FAKE_DIRECTION)
    def test_search_passes_waypoints(self, mock_dir, mock_geo):
        self.srv.json("POST", "/api/config", {"key": "k"})
        _, data = self.srv.json("POST", "/api/search",
                                {"origin": "北京", "destination": "上海", "mode": "driving",
                                 "waypoints": ["116.45,39.92"]})
        self.assertTrue(data["success"])
        self.assertEqual(len(data["route"]["waypoints"]), 1)
        self.assertIsNotNone(mock_dir.call_args[1].get("waypoints"))

    @patch.object(app.amap_client, "geocode", side_effect=fake_geocode)
    @patch.object(app.amap_client, "direction", return_value=FAKE_DIRECTION)
    def test_batch_ok(self, mock_dir, mock_geo):
        self.srv.json("POST", "/api/config", {"key": "k"})
        items = [{"origin": "a", "destination": "b", "mode": "driving", "name": "r1"},
                 {"origin": "c", "destination": "d", "mode": "", "name": "r2"}]
        status, data = self.srv.json("POST", "/api/batch",
                                     {"items": items, "default_mode": "driving"})
        self.assertEqual(status, 200)
        self.assertEqual(data["ok_count"], 2)

    def test_import_csv(self):
        body = "起点,终点,出行方式,备注\n北京,上海,驾车,测试\n".encode("utf-8")
        status, data = self.srv.json(
            "POST", "/api/import", body,
            headers={"Content-Type": "application/octet-stream", "X-Filename": "a.csv"})
        self.assertEqual(status, 200)
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["items"][0]["mode"], "driving")

    def test_export(self):
        route = {"mode": "driving", "mode_label": "驾车",
                 "origin": {"name": "A"}, "destination": {"name": "B"},
                 "distance_m": 1000, "duration_s": 60,
                 "steps": [{"index": 1, "instruction": "直行", "road": "某路", "action": "直行",
                            "orientation": "东", "distance_m": 1000, "duration_s": 60}],
                 "polyline_gcj": [[116.4, 39.9], [116.5, 39.95]],
                 "polyline_wgs": [[116.39, 39.89], [116.49, 39.94]]}
        status, data = self.srv.json("POST", "/api/export", {"kind": "route_geojson", "route": route})
        self.assertEqual(status, 200)
        self.assertTrue(data["success"])
        self.assertIn("/downloads/", data["url"])

    def test_plan_roundtrip(self):
        plan = {"date": "2026-10-21", "items": [{"id": "x", "name": "n", "ts": 1, "route": {}}]}
        status, data = self.srv.json("POST", "/api/plan", {"plan": plan})
        self.assertEqual(status, 200)
        _, data = self.srv.json("GET", "/api/plan")
        self.assertEqual(data["plan"]["items"][0]["id"], "x")

    def test_backup_endpoint(self):
        self.srv.json("POST", "/api/config", {"key": "bk"})
        status, raw = self.srv.request("GET", "/api/backup")
        self.assertEqual(status, 200)
        self.assertTrue(raw.startswith(b"PK"))  # zip 魔数

    def test_restore_endpoint(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("data/config.json", json.dumps({"key": "restored"}))
        status, data = self.srv.json("POST", "/api/restore", buf.getvalue(),
                                     headers={"Content-Type": "application/octet-stream"})
        self.assertEqual(status, 200)
        self.assertTrue(data["success"])
        _, cfg = self.srv.json("GET", "/api/config")
        self.assertEqual(cfg["key"], "restored")

    def test_tile_endpoint(self):
        with patch.object(app, "get_tile", return_value=b"\x89PNGxxx"):
            status, raw = self.srv.request("GET", "/tiles/10/843/388.png")
        self.assertEqual(status, 200)
        self.assertEqual(raw, b"\x89PNGxxx")


class TestSearchRouteTraffic(unittest.TestCase):
    def test_traffic_segments_built(self):
        DIR = {"distance_m": 5000, "duration_s": 600,
               "steps": [
                   {"instruction": "直行", "road": "某路", "action": "直行", "orientation": "东",
                    "distance_m": 1000, "duration_s": 120,
                    "polyline": [[116.4, 39.9], [116.45, 39.92]],
                    "tmcs": [{"status": 1, "distance_m": 500, "polyline": [[116.4, 39.9], [116.42, 39.91]]},
                             {"status": 3, "distance_m": 500, "polyline": [[116.42, 39.91], [116.45, 39.92]]}]},
               ],
               "origin": "116.4,39.9", "destination": "116.5,39.95"}
        with patch.object(app.amap_client, "direction", return_value=DIR):
            route = app.search_route("k", "116.4,39.9", "116.5,39.95", "driving")
        self.assertEqual(len(route["traffic_gcj"]), 2)
        self.assertEqual(route["traffic_gcj"][1]["status"], 3)
        self.assertEqual(len(route["traffic_wgs"]), 2)


class TestSearchTransit(unittest.TestCase):
    def test_search_transit(self):
        TRANSIT_RESULT = {"distance_m": 12345, "duration_s": 1800, "cost": "3",
                          "walking_distance_m": 500,
                          "segments": [
                              {"type": "步行", "name": "步行", "start": "A", "end": "B",
                               "distance_m": 100, "duration_s": 60,
                               "polyline": [[116.4, 39.9], [116.41, 39.91]]},
                              {"type": "地铁", "name": "地铁1号线", "start": "天安门东", "end": "建国门",
                               "distance_m": 5000, "duration_s": 600,
                               "polyline": [[116.41, 39.91], [116.45, 39.93]]}]}
        with patch.object(app.amap_client, "regeo", return_value=("北京", "110000")), \
             patch.object(app.amap_client, "transit", return_value=TRANSIT_RESULT) as mt:
            route = app.search_route("k", "116.4,39.9", "116.5,39.95", "transit")
        self.assertEqual(route["mode"], "transit")
        self.assertEqual(route["cost"], "3")
        self.assertEqual(len(route["segments"]), 2)
        self.assertEqual(route["segments"][1]["name"], "地铁1号线")
        self.assertEqual(mt.call_args[0][3], "北京")


if __name__ == "__main__":
    unittest.main()
