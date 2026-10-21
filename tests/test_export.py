# -*- coding: utf-8 -*-
"""导出函数测试（不联网）。"""
import json
import os
import unittest

import app
from helpers import temp_storage


def _route():
    return {
        "mode": "driving", "mode_label": "驾车",
        "origin": {"name": "A"}, "destination": {"name": "B"},
        "distance_m": 5000, "duration_s": 600,
        "steps": [
            {"index": 1, "instruction": "直行", "road": "某路", "action": "直行",
             "orientation": "东", "distance_m": 1000, "duration_s": 120,
             "polyline_gcj": [[116.4, 39.9], [116.45, 39.92]],
             "polyline_wgs": [[116.39, 39.89], [116.44, 39.91]]},
            {"index": 2, "instruction": "右转", "road": "另一路", "action": "右转",
             "orientation": "南", "distance_m": 4000, "duration_s": 480,
             "polyline_gcj": [[116.45, 39.92], [116.5, 39.95]],
             "polyline_wgs": [[116.44, 39.91], [116.49, 39.94]]},
        ],
        "polyline_gcj": [[116.4, 39.9], [116.45, 39.92], [116.5, 39.95]],
        "polyline_wgs": [[116.39, 39.89], [116.44, 39.91], [116.49, 39.94]],
    }


class TestBuildCsv(unittest.TestCase):
    def test_route_csv_rows(self):
        rows = app.build_route_csv_rows(_route())
        self.assertEqual(rows[0][0], "序号")
        self.assertEqual(len(rows), 3)            # 表头 + 2 行分段
        self.assertEqual(rows[2][-1], 5000)       # 累计距离

    def test_stats_rows_total(self):
        rows = app.build_stats_rows([_route(), _route()])
        self.assertEqual(len(rows), 4)            # 表头 + 2 数据 + 合计
        self.assertEqual(rows[-1][4], "合计")
        self.assertEqual(rows[-1][5], "10.000")

    def test_batch_csv_rows(self):
        rows = app.build_batch_csv_rows([_route()])
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[1][0], 1)           # 路线编号


class TestRouteFeature(unittest.TestCase):
    def test_feature(self):
        f = app.route_feature(_route())
        self.assertEqual(f["type"], "Feature")
        self.assertEqual(f["geometry"]["type"], "LineString")
        self.assertEqual(f["geometry"]["coordinates"][0], [116.39, 39.89])


class TestCsvBytes(unittest.TestCase):
    def test_bom(self):
        data = app.csv_to_bytes([["序号", "距离"], [1, 1000]])
        self.assertTrue(data.startswith(b"\xef\xbb\xbf"))  # UTF-8 BOM


class TestDoExport(unittest.TestCase):
    def test_export_writes_files(self):
        with temp_storage() as (_, downloads):
            r = app.do_export({"kind": "route_csv", "route": _route()})
            self.assertTrue(os.path.isfile(os.path.join(downloads, r["filename"])))
            r2 = app.do_export({"kind": "route_geojson", "route": _route()})
            self.assertTrue(r2["filename"].endswith(".geojson"))
            r3 = app.do_export({"kind": "stats_csv", "routes": [_route()]})
            self.assertTrue(r3["filename"].endswith(".csv"))

    def test_unknown_kind_raises(self):
        with temp_storage():
            with self.assertRaises(ValueError):
                app.do_export({"kind": "nope"})


class TestTrajectoryExport(unittest.TestCase):
    def test_trajectory_geojson(self):
        with temp_storage() as (_, downloads):
            r = app.do_export({"kind": "trajectory_geojson",
                               "points": [[116.39, 39.89], [116.49, 39.94]]})
            with open(os.path.join(downloads, r["filename"]), encoding="utf-8") as f:
                fc = json.load(f)
            g = fc["features"][0]["geometry"]
            self.assertEqual(g["type"], "LineString")
            self.assertEqual(g["coordinates"][0], [116.39, 39.89])
            self.assertEqual(fc["features"][0]["properties"]["points_count"], 2)

    def test_trajectory_csv(self):
        with temp_storage() as (_, downloads):
            r = app.do_export({"kind": "trajectory_csv",
                               "points": [[116.39, 39.89], [116.49, 39.94]]})
            with open(os.path.join(downloads, r["filename"]), "rb") as f:
                text = f.read().decode("utf-8-sig")
            self.assertIn("经度(WGS84)", text)
            self.assertIn("116.39", text)


if __name__ == "__main__":
    unittest.main()
