# -*- coding: utf-8 -*-
"""测试辅助：临时 storage 目录 + 内存 HTTP 服务器。"""
import json
import os
import shutil
import threading
import urllib.error
import urllib.request
import uuid
from contextlib import contextmanager
from http.server import ThreadingHTTPServer

import app as app_module
import storage

# 应用根目录（工作区），临时目录建在这里以通过沙箱写限制
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@contextmanager
def temp_storage():
    """把 storage 的 data/downloads 指向工作区内的临时目录，用完清理并还原。

    注意：不能使用 tempfile.mkdtemp —— 在 DSH 沙箱下 mkdtemp 创建的目录
    不允许再建子目录；改用 os.makedirs（继承父目录 ACL，可写）。
    """
    tmp = os.path.join(BASE, "routetool_test_" + uuid.uuid4().hex[:10])
    os.makedirs(tmp, exist_ok=True)
    old_data, old_download = storage.DATA_DIR, storage.DOWNLOAD_DIR
    storage.DATA_DIR = os.path.join(tmp, "data")
    storage.DOWNLOAD_DIR = os.path.join(tmp, "downloads")
    try:
        yield storage.DATA_DIR, storage.DOWNLOAD_DIR
    finally:
        storage.DATA_DIR, storage.DOWNLOAD_DIR = old_data, old_download
        shutil.rmtree(tmp, ignore_errors=True)


class TestServer:
    """在随机端口启动 app.Handler，隔离 storage 目录。"""

    def __init__(self):
        self._ctx = temp_storage()
        self._ctx.__enter__()
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), app_module.Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = "http://127.0.0.1:%d" % self.server.server_address[1]

    def request(self, method, path, body=None, headers=None):
        data = None
        h = dict(headers or {})
        if body is not None:
            if isinstance(body, (dict, list)):
                data = json.dumps(body).encode("utf-8")
                h.setdefault("Content-Type", "application/json")
            else:
                data = body
        req = urllib.request.Request(self.base + path, data=data, headers=h, method=method)
        try:
            resp = urllib.request.urlopen(req, timeout=20)
            return resp.status, resp.read()
        except urllib.error.HTTPError as e:
            return e.code, e.read()

    def json(self, method, path, body=None, headers=None):
        status, raw = self.request(method, path, body, headers)
        try:
            return status, json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return status, raw

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self._ctx.__exit__(None, None, None)
