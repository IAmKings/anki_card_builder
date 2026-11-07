"""契约单一真值的回归：枚举派生、身份键、定位行。"""

import json
import tempfile
import unittest
from pathlib import Path

from ankicards.schema import (PAGES_ALLOWED, SOURCE_KINDS, card_identity, load_spec,
                              location_label, validate)


def deck(tmp: Path, cards, kind=None):
    (tmp / "cards").mkdir(parents=True, exist_ok=True)
    (tmp / "cards" / "01.json").write_text(
        json.dumps({"deck": "S", "cards": cards}, ensure_ascii=False), encoding="utf-8")
    manifest = {"name": "契约"}
    if kind is not None:
        manifest["source_kind"] = kind
    (tmp / "deck.json").write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    return load_spec(tmp)


class EnumTest(unittest.TestCase):
    def test_pages_allowed_matches_contract(self):
        self.assertIn("pdf", PAGES_ALLOWED)
        self.assertIn("unknown", PAGES_ALLOWED)
        for kind in ("md", "txt", "docx", "image"):
            self.assertNotIn(kind, PAGES_ALLOWED)

    def test_warning_text_lists_every_source_kind(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec = deck(Path(tmp), [{"type": "qa", "q": "q", "a": "a", "pages": [1]}])
            report = validate(spec)
            warning = next(w for w in report.warnings if "source_kind" in w)
            for kind in SOURCE_KINDS - {"unknown"}:
                self.assertIn(kind, warning)

    def test_unknown_kind_with_pages_warns_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec = deck(Path(tmp), [{"type": "qa", "q": "q", "a": "a", "pages": [1]}])
            report = validate(spec)
            self.assertTrue(report.ok)
            self.assertEqual(sum("source_kind" in w for w in report.warnings), 1)


class IdentityTest(unittest.TestCase):
    def test_same_question_different_answer_is_distinct(self):
        self.assertNotEqual(card_identity({"type": "qa", "q": "问", "a": "甲"}),
                            card_identity({"type": "qa", "q": "问", "a": "乙"}))

    def test_same_question_answer_different_image_is_distinct(self):
        self.assertNotEqual(
            card_identity({"type": "image", "q": "问", "a": "答", "img": "a"}),
            card_identity({"type": "image", "q": "问", "a": "答", "img": "b"}))

    def test_whitespace_normalized(self):
        self.assertEqual(card_identity({"type": "qa", "q": "问 题", "a": "答 案"}),
                         card_identity({"type": "qa", "q": "问题", "a": "答案"}))


class LocationLabelTest(unittest.TestCase):
    def test_pages_plus_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec = deck(Path(tmp), [{"type": "qa", "q": "q", "a": "a", "pages": [1, 3],
                                     "source": "x.md"}], kind="pdf")
            self.assertEqual(location_label(spec.sections[0]["cards"][0]), "P1、P3 · x.md")

    def test_source_only_and_escaped(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec = deck(Path(tmp), [{"type": "qa", "q": "q", "a": "a",
                                     "source": "<b>x</b>"}], kind="md")
            label = location_label(spec.sections[0]["cards"][0])
            self.assertNotIn("<b>", label)
            self.assertIn("&lt;b&gt;", label)

    def test_has_pages(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec = deck(Path(tmp), [{"type": "qa", "q": "q", "a": "a",
                                     "source": "x"}], kind="md")
            self.assertFalse(spec.has_pages)


if __name__ == "__main__":
    unittest.main()
