# -*- coding: utf-8 -*-
"""本地 JSON 文件持久化（数据保存在 data/ 目录，重启不丢失）。"""
import json
import os
import threading

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
DOWNLOAD_DIR = os.path.join(BASE_DIR, "downloads")

_lock = threading.Lock()


def _path(name):
    return os.path.join(DATA_DIR, name + ".json")


def _load(name, default):
    p = _path(name)
    if not os.path.exists(p):
        return default
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return default


def _save(name, obj):
    os.makedirs(DATA_DIR, exist_ok=True)
    p = _path(name)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    os.replace(tmp, p)


# ---- 配置（高德 Key）----
def get_key():
    return _load("config", {"key": ""}).get("key", "")


def set_key(key):
    with _lock:
        cfg = _load("config", {"key": ""})
        cfg["key"] = (key or "").strip()
        _save("config", cfg)
    return cfg["key"]


# ---- 搜索历史 ----
def get_history():
    return _load("history", [])


def add_history(entry):
    with _lock:
        h = _load("history", [])
        h.insert(0, entry)
        h = h[:100]
        _save("history", h)
    return h


def delete_history(index):
    with _lock:
        h = _load("history", [])
        if 0 <= index < len(h):
            h.pop(index)
            _save("history", h)
    return h


def clear_history():
    with _lock:
        _save("history", [])
    return []


# ---- 今日计划 ----
def get_plan():
    return _load("plan", {"date": "", "items": []})


def set_plan(plan):
    with _lock:
        _save("plan", plan)
    return plan


def ensure_download_dir():
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    return DOWNLOAD_DIR
