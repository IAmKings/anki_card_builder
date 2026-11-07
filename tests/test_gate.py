"""契约闸门与 HTML 净化的回归测试。"""

import json
import tempfile
import unittest
from pathlib import Path

from ankicards.sanitize import sanitize_html
from ankicards.schema import load_spec, validate


def make_deck(tmp: Path, cards, kind="pdf", cards_name="01.json"):
    (tmp / "cards").mkdir(parents=True, exist_ok=True)
    (tmp / "cards" / cards_name).write_text(
        json.dumps({"deck": "S", "cards": cards}, ensure_ascii=False), encoding="utf-8")
    (tmp / "deck.json").write_text(
        json.dumps({"name": "测试", "source_kind": kind}, ensure_ascii=False), encoding="utf-8")
    return load_spec(tmp)


class GateTest(unittest.TestCase):
    def test_page_must_exist_in_ingest(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec = make_deck(Path(tmp), [{"type": "qa", "q": "q", "a": "a", "pages": [2]}])
            report = validate(spec, page_count=2, ingest={1: "有文本", 2: "有文本"})
            self.assertTrue(report.ok)
            bad = validate(spec, page_count=2, ingest={1: "有文本"})
            self.assertFalse(bad.ok)
            self.assertTrue(any("不在 ingest" in e for e in bad.errors))

    def test_empty_ingest_page_is_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec = make_deck(Path(tmp), [{"type": "qa", "q": "q", "a": "a", "pages": [2]}])
            report = validate(spec, page_count=2, ingest={1: "文本", 2: "   "})
            self.assertFalse(report.ok)
            self.assertTrue(any("没有文本" in e for e in report.errors))

    def test_non_pdf_kind_rejects_pages(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec = make_deck(Path(tmp), [
                {"type": "qa", "q": "q", "a": "a", "pages": [1], "source": "x.md"}], kind="md")
            report = validate(spec)
            self.assertFalse(report.ok)
            self.assertTrue(any("仅表示 PDF 页" in e for e in report.errors))

    def test_unknown_field_is_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec = make_deck(Path(tmp), [
                {"type": "qa", "q": "q", "a": "a", "pages": [1], "locator": {"p": 1}}])
            report = validate(spec)
            self.assertFalse(report.ok)
            self.assertTrue(any("未知字段" in e for e in report.errors))

    def test_unknown_source_kind_warns_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "cards").mkdir()
            (root / "cards" / "01.json").write_text(
                json.dumps({"deck": "S", "cards": [
                    {"type": "qa", "q": "q", "a": "a", "pages": [1]}]}, ensure_ascii=False),
                encoding="utf-8")
            (root / "deck.json").write_text(json.dumps({"name": "无 kind"}), encoding="utf-8")
            report = validate(load_spec(root))
            self.assertTrue(report.ok)
            self.assertEqual(sum("未声明 source_kind" in w for w in report.warnings), 1)


class SanitizeTest(unittest.TestCase):
    def test_removes_script_and_handlers(self):
        dirty = '<b>答案</b><script>alert(1)</script><img src=x onerror="alert(2)">'
        clean = sanitize_html(dirty)
        self.assertNotIn("<script", clean.lower())
        self.assertNotIn("onerror", clean.lower())
        self.assertIn("<b>答案</b>", clean)

    def test_removes_remote_urls(self):
        clean = sanitize_html('<img src="https://evil.invalid/x.gif"><a href="javascript:1">x</a>')
        self.assertNotIn("https://", clean)
        self.assertNotIn("javascript:", clean)

    def test_keeps_relative_media(self):
        clean = sanitize_html('<img class="photo" src="abc-1.jpg">')
        self.assertIn('src="abc-1.jpg"', clean)


if __name__ == "__main__":
    unittest.main()
