"""构建落盘与依赖的回归：out 是目录、缺 genanki 都必须可读退出。"""

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from ankicards.cli import main


def run(args):
    stderr = io.StringIO()
    with contextlib.redirect_stderr(stderr):
        code = main(args)
    return code, stderr.getvalue()


def make_deck(root: Path) -> Path:
    (root / "cards").mkdir(parents=True)
    (root / "deck.json").write_text(
        json.dumps({"name": "IO", "source_kind": "md"}, ensure_ascii=False), encoding="utf-8")
    (root / "cards" / "01.json").write_text(
        json.dumps({"deck": "S", "cards": [
            {"type": "qa", "q": "问", "a": "答", "source": "x"}]}, ensure_ascii=False),
        encoding="utf-8")
    return root


class BuildIOTest(unittest.TestCase):
    def test_out_is_directory_is_exit_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            deck = make_deck(Path(tmp) / "deck")
            code, err = run(["build", str(deck), "--out", tmp])
            self.assertEqual(code, 2)
            self.assertNotIn("Traceback", err)

    def test_missing_genanki_is_exit_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            deck = make_deck(Path(tmp) / "deck")
            with mock.patch.dict(sys.modules, {"genanki": None}):
                code, err = run(["build", str(deck), "--out", str(Path(tmp) / "x.apkg")])
            self.assertEqual(code, 2)
            self.assertNotIn("Traceback", err)
            self.assertIn("genanki", err)

    def test_normal_build_still_works(self):
        with tempfile.TemporaryDirectory() as tmp:
            deck = make_deck(Path(tmp) / "deck")
            out = Path(tmp) / "x.apkg"
            code, err = run(["build", str(deck), "--out", str(out)])
            self.assertEqual(code, 0, err)
            self.assertTrue(out.exists())


if __name__ == "__main__":
    unittest.main()
