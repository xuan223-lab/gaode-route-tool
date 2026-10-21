# -*- coding: utf-8 -*-
"""测试运行器：python run_tests.py"""
import os
import shutil
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))


def check_js():
    """用 node --check 校验前端 JS 语法（本机无 node 则跳过）。"""
    node = shutil.which("node")
    if not node:
        print("(未检测到 node，跳过前端 JS 语法校验)")
        return True
    r = subprocess.run([node, "--check", os.path.join(ROOT, "static", "app.js")],
                       capture_output=True, text=True)
    if r.returncode != 0:
        print("前端 app.js 语法错误：\n" + r.stderr)
        return False
    print("前端 app.js 语法 OK")
    return True


if __name__ == "__main__":
    if not check_js():
        sys.exit(1)
    suite = unittest.defaultTestLoader.discover(os.path.join(ROOT, "tests"))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
