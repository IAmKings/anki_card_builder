"""闸门顺序与错误类型：数据错误优先于闸门，闸门失败用 GateError(code=1)。"""

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from ankicards.cli import main
from ankicards.errors import CardError


def run(args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(args)
    return code, out.getvalue() + err.getvalue()


def make_deck(root: Path, cards) -> Path:
    (root / "cards").mkdir(parents=True)
    (root / "deck.json").write_text(
        json.dumps({"name": "闸门", "source_kind": "pdf"}, ensure_ascii=False), encoding="utf-8")
    (root / "cards" / "01.json").write_text(
        json.dumps({"deck": "S", "cards": cards}, ensure_ascii=False), encoding="utf-8")
    return root


class GateOrderTest(unittest.TestCase):
    def test_type_error_not_masked_by_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            deck = make_deck(Path(tmp), [
                {"type": "qa", "q": "q", "a": "a", "pages": "5"}])
            code, output = run(["build", str(deck), "--out", str(Path(tmp) / "x.apkg")])
            self.assertEqual(code, 1, output)
            self.assertIn("pages 必须是非空数组", output)
            self.assertNotIn("请先 ingest", output)

    def test_warning_report_printed_before_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            deck = make_deck(Path(tmp), [
                {"type": "qa", "q": "同一问题", "a": "同一答案", "pages": [1]},
                {"type": "qa", "q": "同一问题", "a": "同一答案", "pages": [1]},
            ])
            code, output = run(["build", str(deck), "--out", str(Path(tmp) / "x.apkg")])
            self.assertEqual(code, 1, output)
            self.assertIn("身份重复", output)
            self.assertIn("--ingest", output)

    def test_gate_still_blocks_valid_deck(self):
        with tempfile.TemporaryDirectory() as tmp:
            deck = make_deck(Path(tmp), [
                {"type": "qa", "q": "q", "a": "a", "pages": [1]}])
            code, output = run(["build", str(deck), "--out", str(Path(tmp) / "x.apkg")])
            self.assertEqual(code, 1, output)
            self.assertIn("--ingest", output)


class GateErrorContractTest(unittest.TestCase):
    def test_gate_error_is_card_error_with_code_1(self):
        from ankicards import errors

        self.assertTrue(hasattr(errors, "GateError"), "缺少 GateError")
        self.assertTrue(issubclass(errors.GateError, CardError))
        self.assertEqual(errors.GateError.code, 1)
        self.assertEqual(CardError.code, 2)


if __name__ == "__main__":
    unittest.main()
