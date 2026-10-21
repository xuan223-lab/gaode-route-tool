# -*- coding: utf-8 -*-
"""备份 / 恢复函数测试。"""
import io
import json
import os
import unittest
import zipfile

import app
import storage
from helpers import temp_storage


def _make_zip(files):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for name, content in files.items():
            z.writestr(name, content)
    return buf.getvalue()


class TestBackupRestore(unittest.TestCase):
    def test_backup_contains_data_and_downloads(self):
        with temp_storage():
            storage.set_key("abc")
            storage.ensure_download_dir()
            with open(os.path.join(storage.DOWNLOAD_DIR, "x.csv"), "w", encoding="utf-8") as f:
                f.write("a,b")
            data = app.backup_to_zip()
            names = zipfile.ZipFile(io.BytesIO(data)).namelist()
            self.assertIn("data/config.json", names)
            self.assertIn("downloads/x.csv", names)

    def test_restore_writes_config(self):
        with temp_storage():
            zip_data = _make_zip({"data/config.json": json.dumps({"key": "restored_key"})})
            app.restore_from_zip(zip_data)
            self.assertEqual(storage.get_key(), "restored_key")

    def test_restore_backs_up_old_data(self):
        with temp_storage():
            storage.set_key("old")
            zip_data = _make_zip({"data/config.json": json.dumps({"key": "new"})})
            app.restore_from_zip(zip_data)
            self.assertEqual(storage.get_key(), "new")
            parent = os.path.dirname(storage.DATA_DIR)
            backups = os.path.join(parent, "backups")
            self.assertTrue(os.path.isdir(backups))
            sub = [d for d in os.listdir(backups) if d.startswith("pre-restore-")]
            self.assertEqual(len(sub), 1)
            old_cfg = os.path.join(backups, sub[0], "data", "config.json")
            with open(old_cfg, encoding="utf-8") as f:
                self.assertEqual(json.load(f)["key"], "old")


if __name__ == "__main__":
    unittest.main()
