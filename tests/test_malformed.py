"""畸形输入回归：文件编码/结构错误必须给可读文案与正确退出码，不能 traceback。

错误分类（与 README 退出码表一致）：
- 2：用法/环境/文件形状错误（非 UTF-8、非对象数组、坏 ingest 结构）
- 1：数据错误（字段类型不对）
"""

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from ankicards.cli import main


def run(args):
    stderr = io.StringIO()
    with contextlib.redirect_stderr(stderr):
        code = main(args)
    return code, stderr.getvalue()


def make_deck(root: Path, deck_json, cards_json, crops_json=None):
    (root / "cards").mkdir(parents=True, exist_ok=True)
    (root / "deck.json").write_bytes(
        deck_json if isinstance(deck_json, bytes) else deck_json.encode("utf-8"))
    (root / "cards" / "01.json").write_bytes(
        cards_json if isinstance(cards_json, bytes) else cards_json.encode("utf-8"))
    if crops_json is not None:
        (root / "crops.json").write_bytes(
            crops_json if isinstance(crops_json, bytes) else crops_json.encode("utf-8"))


GOOD_DECK = json.dumps({"name": "畸形", "source_kind": "md"}, ensure_ascii=False)
GOOD_CARDS = json.dumps({"deck": "S", "cards": [
    {"type": "qa", "q": "问", "a": "答", "source": "x"}]}, ensure_ascii=False)


class MalformedDeckTest(unittest.TestCase):
    def test_non_utf8_deck_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            make_deck(Path(tmp), b"\xff\xfe", GOOD_CARDS)
            code, err = run(["check", str(tmp)])
            self.assertEqual(code, 2)
            self.assertNotIn("Traceback", err)

    def test_non_utf8_cards_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            make_deck(Path(tmp), GOOD_DECK, b"\xff\xfe")
            code, err = run(["check", str(tmp)])
            self.assertEqual(code, 2)
            self.assertNotIn("Traceback", err)

    def test_non_utf8_crops_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            make_deck(Path(tmp), GOOD_DECK, GOOD_CARDS, crops_json=b"\xff\xfe")
            code, err = run(["check", str(tmp)])
            self.assertEqual(code, 2)
            self.assertNotIn("Traceback", err)

    def test_cards_must_be_object_array(self):
        with tempfile.TemporaryDirectory() as tmp:
            make_deck(Path(tmp), GOOD_DECK, json.dumps({"deck": "S", "cards": ["x"]}))
            code, err = run(["check", str(tmp)])
            self.assertEqual(code, 2)
            self.assertIn("对象数组", err)
            self.assertNotIn("Traceback", err)

    def test_question_wrong_type_is_data_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            make_deck(Path(tmp), GOOD_DECK, json.dumps({"deck": "S", "cards": [
                {"type": "qa", "q": ["x"], "a": "a", "source": "x"}]}))
            code, err = run(["check", str(tmp)])
            self.assertEqual(code, 1)
            self.assertNotIn("Traceback", err)


class MalformedIngestTest(unittest.TestCase):
    def _deck(self, tmp: Path) -> Path:
        make_deck(tmp, GOOD_DECK, GOOD_CARDS)
        return tmp

    def test_ingest_top_level_array(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ing.json"
            path.write_text("[1,2]", encoding="utf-8")
            code, err = run(["check", str(self._deck(Path(tmp) / "deck")), "--ingest", str(path)])
            self.assertEqual(code, 2)
            self.assertNotIn("Traceback", err)

    def test_ingest_units_must_be_objects(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ing.json"
            path.write_text('{"units":[1,2]}', encoding="utf-8")
            code, err = run(["check", str(self._deck(Path(tmp) / "deck")), "--ingest", str(path)])
            self.assertEqual(code, 2)
            self.assertNotIn("Traceback", err)

    def test_ingest_non_utf8(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ing.json"
            path.write_bytes(b"\xff\xfe")
            code, err = run(["check", str(self._deck(Path(tmp) / "deck")), "--ingest", str(path)])
            self.assertEqual(code, 2)
            self.assertNotIn("Traceback", err)


if __name__ == "__main__":
    unittest.main()
