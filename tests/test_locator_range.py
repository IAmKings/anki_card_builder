"""区间定位：line/para/block 的 N-M 语法、次序检查与 ingest 存在性。"""

import json
import tempfile
import unittest
from pathlib import Path

from ankicards.schema import (
    DOCX_LOCATOR_RE, TXT_LOCATOR_RE, WEB_LOCATOR_RE, load_spec, parse_locator,
    validate,
)


def make_deck(root: Path, source_kind: str, source: str) -> Path:
    (root / "cards").mkdir(parents=True)
    (root / "deck.json").write_text(
        json.dumps({"name": "区间定位", "source_kind": source_kind}, ensure_ascii=False),
        encoding="utf-8")
    (root / "cards" / "01.json").write_text(json.dumps({
        "deck": "区间", "cards": [
            {"type": "qa", "q": "问", "a": "答", "source": source}],
    }, ensure_ascii=False), encoding="utf-8")
    return root


class ParseLocatorTest(unittest.TestCase):
    def test_single_and_range(self):
        self.assertEqual(parse_locator("line:3"), ("line", 3, 3))
        self.assertEqual(parse_locator("line:3-7"), ("line", 3, 7))
        self.assertEqual(parse_locator("para:12-14"), ("para", 12, 14))
        self.assertEqual(parse_locator("block:2-9"), ("block", 2, 9))

    def test_table(self):
        self.assertEqual(parse_locator("table:1/r2"), ("table", 1, 2))

    def test_rejects_illegal(self):
        for value in ("", "line:0", "line:3-0", "line:3-7-9", "para:x", "block:1/2"):
            self.assertIsNone(parse_locator(value), value)

    def test_regex_accepts_ranges(self):
        self.assertTrue(TXT_LOCATOR_RE.fullmatch("line:3-7"))
        self.assertTrue(DOCX_LOCATOR_RE.fullmatch("para:3-7"))
        self.assertTrue(DOCX_LOCATOR_RE.fullmatch("table:1/r2"))
        self.assertTrue(WEB_LOCATOR_RE.fullmatch("block:3-7"))


class RangeValidateTest(unittest.TestCase):
    def test_txt_range_present_in_ingest_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            deck = make_deck(Path(tmp) / "deck", "txt", "line:2-4")
            report = validate(load_spec(deck), locators={"line:2-4": "甲 乙 丙"})
            self.assertTrue(report.ok, report.errors)

    def test_range_missing_from_ingest_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            deck = make_deck(Path(tmp) / "deck", "txt", "line:2-4")
            report = validate(load_spec(deck), locators={"line:2": "甲"})
            self.assertFalse(report.ok)
            self.assertIn("不在 ingest 产物中", " ".join(report.errors))

    def test_inverted_range_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            deck = make_deck(Path(tmp) / "deck", "txt", "line:4-2")
            report = validate(load_spec(deck), locators={"line:4-2": "甲"})
            self.assertFalse(report.ok)
            self.assertIn("区间倒置", " ".join(report.errors))

    def test_docx_and_web_ranges_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            for kind, source in (("docx", "para:3-5"), ("web", "block:2-3")):
                deck = make_deck(Path(tmp) / kind, kind, source)
                report = validate(load_spec(deck), locators={source: "文本"})
                self.assertTrue(report.ok, report.errors)

    def test_empty_range_text_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            deck = make_deck(Path(tmp) / "deck", "txt", "line:2-4")
            report = validate(load_spec(deck), locators={"line:2-4": "  "})
            self.assertFalse(report.ok)
            self.assertIn("没有文本", " ".join(report.errors))


if __name__ == "__main__":
    unittest.main()
