# -*- coding: utf-8 -*-
"""瓦片缓存测试。"""
import os
import shutil
import unittest
import uuid
from unittest.mock import patch

import app

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestTile(unittest.TestCase):
    def setUp(self):
        self.tiles = os.path.join(BASE, "tiles_test_" + uuid.uuid4().hex[:8])
        os.makedirs(self.tiles, exist_ok=True)
        self.old = app.TILES_DIR
        app.TILES_DIR = self.tiles

    def tearDown(self):
        app.TILES_DIR = self.old
        shutil.rmtree(self.tiles, ignore_errors=True)

    def test_invalid_params(self):
        self.assertIsNone(app.get_tile("abc", "1", "1"))
        self.assertIsNone(app.get_tile("25", "1", "1"))

    def test_cache_and_serve(self):
        png = b"\x89PNG fake tile bytes"
        with patch.object(app.urllib.request, "urlopen") as mock_open:
            mock_open.return_value.__enter__.return_value.read.return_value = png
            data1 = app.get_tile("10", "843", "388")
            self.assertEqual(data1, png)
            self.assertEqual(mock_open.call_count, 1)
            data2 = app.get_tile("10", "843", "388")
            self.assertEqual(data2, png)
            self.assertEqual(mock_open.call_count, 1)  # 命中缓存，不再联网
        self.assertTrue(os.path.isfile(os.path.join(self.tiles, "10", "843", "388.png")))


if __name__ == "__main__":
    unittest.main()
