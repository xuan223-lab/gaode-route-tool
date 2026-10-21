# -*- coding: utf-8 -*-
"""amap_client 解析函数测试（不联网，用固定样例）。"""
import unittest
from unittest.mock import patch
from urllib.parse import urlparse, parse_qs

import amap_client
from amap_client import AmapError


def _driving():
    return {
        "status": "1", "info": "OK", "infocode": "10000",
        "route": {
            "origin": "116.4,39.9", "destination": "116.5,39.95",
            "paths": [{
                "distance": "5000", "duration": "600",
                "steps": [
                    {"instruction": "直行", "road": "某路", "action": "直行",
                     "orientation": "东", "distance": "1000", "duration": "120",
                     "polyline": "116.4,39.9;116.45,39.92"},
                    {"instruction": "右转", "road": "另一路", "action": "右转",
                     "orientation": "南", "distance": "4000", "duration": "480",
                     "polyline": "116.45,39.92;116.5,39.95"},
                ],
            }],
        },
    }


def _riding():
    # 官方 v4 骑行示例：data 下直接是 paths/origin/destination
    return {
        "errcode": 0, "errmsg": "OK",
        "data": {
            "origin": "116.434307,39.90909", "destination": "116.434446,39.90816",
            "paths": [{
                "distance": 217, "duration": 52,
                "steps": [
                    {"action": "右转", "distance": 54, "duration": 13,
                     "instruction": "骑行54米右转", "orientation": "",
                     "polyline": "116.434323,39.909049;116.434965,39.909049", "road": ""},
                ],
            }],
        },
    }


class TestParseDirection(unittest.TestCase):
    def test_driving(self):
        r = amap_client._parse_direction(_driving(), "driving")
        self.assertEqual(r["distance_m"], 5000)
        self.assertEqual(r["duration_s"], 600)
        self.assertEqual(len(r["steps"]), 2)
        self.assertEqual(r["steps"][0]["road"], "某路")
        self.assertEqual(len(r["steps"][0]["polyline"]), 2)

    def test_walking_same_as_v3(self):
        r = amap_client._parse_direction(_driving(), "walking")
        self.assertEqual(r["distance_m"], 5000)

    def test_riding_v4(self):
        r = amap_client._parse_direction(_riding(), "riding")
        self.assertEqual(r["distance_m"], 217)
        self.assertEqual(r["duration_s"], 52)
        self.assertEqual(len(r["steps"]), 1)
        self.assertEqual(r["origin"], "116.434307,39.90909")

    def test_error_status_raises(self):
        data = {"status": "0", "info": "INVALID_USER_KEY"}
        with self.assertRaises(AmapError):
            amap_client._parse_direction(data, "driving")

    def test_no_paths_raises(self):
        data = {"status": "1", "route": {"paths": []}}
        with self.assertRaises(AmapError):
            amap_client._parse_direction(data, "driving")


class TestHelpers(unittest.TestCase):
    def test_parse_polyline(self):
        self.assertEqual(amap_client._parse_polyline("116.4,39.9;116.5,39.95"),
                         [[116.4, 39.9], [116.5, 39.95]])

    def test_parse_polyline_empty(self):
        self.assertEqual(amap_client._parse_polyline(""), [])

    def test_to_int(self):
        self.assertEqual(amap_client._to_int("5000"), 5000)
        self.assertEqual(amap_client._to_int(217), 217)
        self.assertEqual(amap_client._to_int("abc"), 0)
        self.assertEqual(amap_client._to_int(None), 0)


class TestDirectionParams(unittest.TestCase):
    OK = {"status": "1", "route": {"paths": [{"distance": "1", "duration": "1", "steps": []}]}}

    @patch.object(amap_client, "_http_get_json", return_value=OK)
    def test_strategy_passed_for_driving(self, mock_get):
        amap_client.direction("k", "driving", (116.4, 39.9), (116.5, 39.95), strategy="6")
        q = parse_qs(urlparse(mock_get.call_args[0][0]).query)
        self.assertEqual(q["strategy"][0], "6")

    @patch.object(amap_client, "_http_get_json", return_value=OK)
    def test_no_strategy_for_walking(self, mock_get):
        amap_client.direction("k", "walking", (116.4, 39.9), (116.5, 39.95))
        q = parse_qs(urlparse(mock_get.call_args[0][0]).query)
        self.assertNotIn("strategy", q)

    @patch.object(amap_client, "_http_get_json", return_value=OK)
    def test_waypoints_passed_for_driving(self, mock_get):
        amap_client.direction("k", "driving", (116.4, 39.9), (116.5, 39.95), waypoints="116.45,39.92")
        q = parse_qs(urlparse(mock_get.call_args[0][0]).query)
        self.assertEqual(q["waypoints"][0], "116.45,39.92")

    @patch.object(amap_client, "_http_get_json", return_value=OK)
    def test_no_waypoints_for_walking(self, mock_get):
        amap_client.direction("k", "walking", (116.4, 39.9), (116.5, 39.95), waypoints="116.45,39.92")
        q = parse_qs(urlparse(mock_get.call_args[0][0]).query)
        self.assertNotIn("waypoints", q)


class TestTmcs(unittest.TestCase):
    def test_tmcs_extracted(self):
        data = {
            "status": "1", "info": "OK",
            "route": {
                "origin": "116.4,39.9", "destination": "116.5,39.95",
                "paths": [{
                    "distance": "5000", "duration": "600",
                    "steps": [{
                        "instruction": "直行", "road": "某路", "action": "直行",
                        "orientation": "东", "distance": "1000", "duration": "120",
                        "polyline": "116.4,39.9;116.45,39.92",
                        "tmcs": [
                            {"lcode": "1", "distance": "500", "status": "1",
                             "polyline": "116.4,39.9;116.42,39.91"},
                            {"lcode": "2", "distance": "500", "status": "3",
                             "polyline": "116.42,39.91;116.45,39.92"},
                        ],
                    }],
                }],
            },
        }
        r = amap_client._parse_direction(data, "driving")
        self.assertEqual(len(r["steps"][0]["tmcs"]), 2)
        self.assertEqual(r["steps"][0]["tmcs"][1]["status"], 3)
        self.assertEqual(len(r["steps"][0]["tmcs"][1]["polyline"]), 2)


def _transit():
    return {
        "status": "1", "info": "OK",
        "route": {
            "origin": "116.4,39.9", "destination": "116.5,39.95",
            "transits": [{
                "cost": "3", "duration": "1800", "walking_distance": "500", "distance": "12345",
                "segments": [
                    {"walking": {"origin": "A", "destination": "B", "distance": "100", "duration": "60",
                                 "steps": [{"polyline": "116.4,39.9;116.41,39.91"}]}},
                    {"bus": {"buslines": [{"name": "地铁1号线", "type": "地铁线路",
                                          "departure_stop": {"name": "天安门东"},
                                          "arrival_stop": {"name": "建国门"},
                                          "distance": "5000", "duration": "600",
                                          "polyline": "116.41,39.91;116.45,39.93"}]}},
                    {"walking": {"origin": "C", "destination": "D", "distance": "200", "duration": "120",
                                 "steps": [{"polyline": "116.45,39.93;116.5,39.95"}]}},
                ],
            }],
        },
    }


class TestParseTransit(unittest.TestCase):
    def test_transit_segments(self):
        r = amap_client._parse_transit(_transit())
        self.assertEqual(r["distance_m"], 12345)
        self.assertEqual(r["cost"], "3")
        self.assertEqual(len(r["segments"]), 3)
        self.assertEqual(r["segments"][0]["type"], "步行")
        self.assertEqual(r["segments"][1]["type"], "地铁")
        self.assertEqual(r["segments"][1]["name"], "地铁1号线")
        self.assertEqual(r["segments"][1]["start"], "天安门东")

    def test_transit_privilege_error_message(self):
        with self.assertRaises(AmapError) as ctx:
            amap_client._parse_transit({"status": "0", "info": "INSUFFICIENT_PRIVILEGES",
                                        "infocode": "10012"})
        self.assertIn("没有", str(ctx.exception))
        self.assertIn("公交", str(ctx.exception))


class TestFriendlyError(unittest.TestCase):
    def test_code_mapping_distance(self):
        msg = amap_client.friendly_error("起点终点距离过长", "20803")
        self.assertIn("距离过长", msg)
        self.assertIn("驾车", msg)

    def test_keyword_mapping(self):
        self.assertIn("没有", amap_client.friendly_error("INSUFFICIENT_PRIVILEGES", ""))

    def test_fallback_unknown(self):
        self.assertEqual(amap_client.friendly_error("SOME_UNKNOWN_ERR", ""), "SOME_UNKNOWN_ERR")

    def test_direction_distance_too_far(self):
        data = {"status": "0", "info": "起点终点距离过长", "infocode": "20803"}
        with self.assertRaises(AmapError) as ctx:
            amap_client._parse_direction(data, "walking")
        self.assertIn("距离过长", str(ctx.exception))
        self.assertIn("驾车", str(ctx.exception))


class TestGeocodeRgeoError(unittest.TestCase):
    @patch.object(amap_client, "_http_get_json",
                  return_value={"status": "0", "info": "INVALID_USER_KEY", "infocode": "10001"})
    def test_geocode_invalid_key_friendly(self, mock_get):
        with self.assertRaises(AmapError) as ctx:
            amap_client.geocode("k", "天安门")
        self.assertIn("Key", str(ctx.exception))
        self.assertNotIn("INVALID_USER_KEY", str(ctx.exception))

    @patch.object(amap_client, "_http_get_json",
                  return_value={"status": "0", "info": "INSUFFICIENT_PRIVILEGES", "infocode": "10012"})
    def test_regeo_privilege_friendly(self, mock_get):
        with self.assertRaises(AmapError) as ctx:
            amap_client.regeo("k", 116.4, 39.9)
        self.assertIn("权限", str(ctx.exception))
        self.assertNotIn("INSUFFICIENT_PRIVILEGES", str(ctx.exception))

    @patch.object(amap_client, "_http_get_json",
                  return_value={"status": "1", "info": "OK"})
    def test_geocode_no_result_friendly(self, mock_get):
        with self.assertRaises(AmapError) as ctx:
            amap_client.geocode("k", "不存在的地方")
        self.assertIn("未找到", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
