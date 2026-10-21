# -*- coding: utf-8 -*-
"""前端资源一致性测试：CSS 语法、HTML 引用、关键类名覆盖。"""
import os
import re
import unittest

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC = os.path.join(BASE, "static")


def _read(name):
    with open(os.path.join(STATIC, name), encoding="utf-8") as f:
        return f.read()


class TestCssSyntax(unittest.TestCase):
    def test_braces_balanced(self):
        css = _read("style.css")
        self.assertEqual(css.count("{"), css.count("}"), "CSS 花括号不匹配")

    def test_non_empty(self):
        css = _read("style.css")
        self.assertGreater(len(css.strip()), 500, "CSS 内容过少")


class TestHtmlLinks(unittest.TestCase):
    def test_references_css(self):
        html = _read("index.html")
        self.assertIn('href="/static/style.css"', html)
        self.assertIn('href="/static/leaflet/leaflet.css"', html)

    def test_references_js(self):
        html = _read("index.html")
        self.assertIn('src="/static/app.js"', html)
        self.assertIn('src="/static/leaflet/leaflet.js"', html)


class TestCssCoverage(unittest.TestCase):
    # 页面结构使用、且必须在 style.css 中定义的关键类
    REQUIRED_CLASSES = [
        "topbar", "tabs", "tab", "panel", "card", "card-title",
        "mode-group", "mode-btn", "summary", "summary-item",
        "result-actions", "table-wrap", "history-list", "row",
        "muted", "small", "hidden", "toast", "badge", "primary",
        "link-btn", "plan-op", "conv-result", "input-row",
        "search-layout", "side",
    ]

    def test_key_classes_defined(self):
        css = _read("style.css")
        html = _read("index.html")
        missing = []
        for cls in self.REQUIRED_CLASSES:
            used = bool(re.search(r'class="[^"]*\b%s\b' % re.escape(cls), html))
            defined = ("." + cls) in css
            if used and not defined:
                missing.append(cls)
        self.assertEqual(missing, [], "页面使用但 CSS 未定义的类: %s" % missing)

    def test_important_ids_exist(self):
        html = _read("index.html")
        for eid in ["map", "originInput", "destInput", "searchBtn", "stepsTable"]:
            self.assertIn('id="%s"' % eid, html)


if __name__ == "__main__":
    unittest.main()
