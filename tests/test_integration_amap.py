# -*- coding: utf-8 -*-
"""真实高德接口联调测试（需要 data/config.json 已配置 Key + 联网）。"""
import json
import os
import unittest

import amap_client

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _real_key():
    try:
        with open(os.path.join(BASE, "data", "config.json"), encoding="utf-8") as f:
            return (json.load(f).get("key") or "").strip()
    except Exception:
        return ""


class TestAmapLive(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.key = _real_key()

    def test_key_configured(self):
        self.assertTrue(self.key, "data/config.json 未配置高德 Key，无法联调")

    def test_geocode_live(self):
        lng, lat, name = amap_client.geocode(self.key, "天安门")
        self.assertGreater(lng, 116.0)
        self.assertLess(lng, 117.0)
        self.assertTrue(name)

    def test_direction_driving_live(self):
        r = amap_client.direction(self.key, "driving",
                                  (116.434307, 39.90909), (116.434446, 39.90816))
        self.assertGreater(r["distance_m"], 0)
        self.assertGreater(r["duration_s"], 0)
        self.assertTrue(r["steps"])

    def test_direction_walking_live(self):
        r = amap_client.direction(self.key, "walking",
                                  (116.434307, 39.90909), (116.434446, 39.90816))
        self.assertGreater(r["distance_m"], 0)

    def test_direction_riding_live(self):
        r = amap_client.direction(self.key, "riding",
                                  (116.434307, 39.90909), (116.434446, 39.90816))
        self.assertGreater(r["distance_m"], 0)


if __name__ == "__main__":
    unittest.main()
