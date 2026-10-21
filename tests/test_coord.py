# -*- coding: utf-8 -*-
"""coord 模块：GCJ-02 ↔ WGS84 互转与坐标解析。"""
import unittest

from coord import wgs84_to_gcj02, gcj02_to_wgs84, parse_coord


class TestWgsToGcj(unittest.TestCase):
    def test_known_offset(self):
        lng, lat = wgs84_to_gcj02(116.397428, 39.90923)
        self.assertAlmostEqual(lng, 116.403672, places=5)
        self.assertAlmostEqual(lat, 39.910634, places=5)

    def test_round_trip(self):
        lng, lat = 116.397428, 39.90923
        g = wgs84_to_gcj02(lng, lat)
        back = gcj02_to_wgs84(*g)
        self.assertAlmostEqual(back[0], lng, places=5)
        self.assertAlmostEqual(back[1], lat, places=5)


class TestGcjToWgs(unittest.TestCase):
    def test_known_offset(self):
        lng, lat = gcj02_to_wgs84(116.481028, 39.989643)
        self.assertAlmostEqual(lng, 116.474940, places=5)
        self.assertAlmostEqual(lat, 39.988362, places=5)

    def test_out_of_china_unchanged(self):
        # 境外坐标不做偏移
        lng, lat = wgs84_to_gcj02(-122.4194, 37.7749)
        self.assertAlmostEqual(lng, -122.4194, places=6)
        self.assertAlmostEqual(lat, 37.7749, places=6)


class TestParseCoord(unittest.TestCase):
    def test_lng_lat_comma(self):
        self.assertEqual(parse_coord("116.397428,39.90923"),
                         (116.397428, 39.90923))

    def test_lng_lat_space(self):
        self.assertEqual(parse_coord("116.397428 39.90923"),
                         (116.397428, 39.90923))

    def test_chinese_comma(self):
        self.assertEqual(parse_coord("116.397428，39.90923"),
                         (116.397428, 39.90923))

    def test_reversed_auto_correct(self):
        # 写反了（纬度,经度）应自动纠正为 (lng, lat)
        lng, lat = parse_coord("39.90923,116.397428")
        self.assertAlmostEqual(lng, 116.397428, places=6)
        self.assertAlmostEqual(lat, 39.90923, places=6)

    def test_address_returns_none(self):
        self.assertIsNone(parse_coord("北京市朝阳区"))

    def test_single_number_returns_none(self):
        self.assertIsNone(parse_coord("116.397"))


if __name__ == "__main__":
    unittest.main()
