# -*- coding: utf-8 -*-
"""paths 模块测试：源码运行与 exe(frozen) 运行两种模式的路径解析。"""
import os
import sys
import unittest
from unittest.mock import patch

import paths


class TestPaths(unittest.TestCase):
    def test_source_mode_base_dir(self):
        # 非 frozen：基准目录为源码所在目录
        with patch.object(sys, "frozen", False, create=True):
            base = paths.app_base_dir()
        self.assertTrue(os.path.isdir(base))
        self.assertTrue(os.path.isfile(os.path.join(base, "app.py")))

    def test_frozen_mode_uses_exe_dir(self):
        # frozen：基准目录为 exe 所在目录，而非临时解压目录
        with patch.object(sys, "frozen", True, create=True), \
             patch.object(sys, "executable", r"C:\Users\demo\Desktop\RouteTool\RouteTool.exe"), \
             patch.object(sys, "_MEIPASS", r"C:\Temp\_MEI123", create=True):
            base = paths.app_base_dir()
            res = paths.resource_dir()
        self.assertEqual(base, r"C:\Users\demo\Desktop\RouteTool")
        self.assertNotIn("_MEI", base)

    def test_frozen_resource_dir_is_meipass(self):
        # frozen：静态资源来自 PyInstaller 临时解压目录
        with patch.object(sys, "frozen", True, create=True), \
             patch.object(sys, "executable", r"C:\demo\RouteTool.exe"), \
             patch.object(sys, "_MEIPASS", r"C:\Temp\_MEI123", create=True):
            self.assertEqual(paths.resource_dir(), r"C:\Temp\_MEI123")

    def test_source_mode_resource_dir_equals_base(self):
        with patch.object(sys, "frozen", False, create=True):
            self.assertEqual(paths.resource_dir(), paths.app_base_dir())


class TestStorageUsesBaseDir(unittest.TestCase):
    def test_data_dir_under_base(self):
        import storage
        self.assertEqual(os.path.dirname(storage.DATA_DIR), paths.app_base_dir())
        self.assertEqual(os.path.dirname(storage.DOWNLOAD_DIR), paths.app_base_dir())


if __name__ == "__main__":
    unittest.main()
