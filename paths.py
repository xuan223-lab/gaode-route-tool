# -*- coding: utf-8 -*-
"""路径解析：兼容"源码运行"与"PyInstaller 打包成 exe 运行"两种方式。

- 源码运行：数据目录 = 项目目录。
- exe 运行：数据目录 = exe 所在目录（用户可见、可持久化），
  而 static/ 等打包资源位于 PyInstaller 的临时解压目录（sys._MEIPASS）。
"""
import os
import sys


def app_base_dir():
    """数据目录基准：exe 所在目录，或源码所在目录。"""
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def resource_dir():
    """打包资源目录：exe 运行时为临时解压目录，源码运行时为项目目录。"""
    return getattr(sys, "_MEIPASS", app_base_dir())
