# -*- coding: utf-8 -*-
"""storage 本地持久化测试。"""
import unittest

import storage
from helpers import temp_storage


class TestStorage(unittest.TestCase):
    def test_key_roundtrip(self):
        with temp_storage():
            storage.set_key("  abc123  ")
            self.assertEqual(storage.get_key(), "abc123")

    def test_history_insert_front_and_cap(self):
        with temp_storage():
            for i in range(105):
                storage.add_history({"id": str(i), "ts": i})
            h = storage.get_history()
            self.assertEqual(len(h), 100)          # 上限 100
            self.assertEqual(h[0]["id"], "104")    # 最新在前

    def test_delete_history(self):
        with temp_storage():
            storage.add_history({"id": "1"})
            storage.add_history({"id": "2"})
            storage.delete_history(0)              # 删除最新的一条 "2"
            self.assertEqual([x["id"] for x in storage.get_history()], ["1"])

    def test_plan_roundtrip(self):
        with temp_storage():
            plan = {"date": "2026-10-21", "items": [{"id": "a"}]}
            storage.set_plan(plan)
            self.assertEqual(storage.get_plan()["items"][0]["id"], "a")


if __name__ == "__main__":
    unittest.main()
