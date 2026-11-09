"""DOCX 源码定位闸门与 CLI：para:N / table:T/rR 必须存在且有文本。"""

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

try:
    import docx  # type: ignore
    HAS_DOCX = True
except ImportError:  # pragma: no cover
    HAS_DOCX = False

from ankicards import ingest as ingest_mod
from ankicards.cli import main
from ankicards.errors import GateError
from ankicards.schema import load_spec, validate


def run(args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(args)
    return code, out.getvalue() + err.getvalue()


def make_docx(path: Path, paragraphs, table_rows=None) -> None:
    doc = docx.Document()
    for text in paragraphs:
        doc.add_paragraph(text)
    if table_rows:
        table = doc.add_table(rows=len(table_rows), cols=len(table_rows[0]))
        for r, row in enumerate(table_rows):
            for c, value in enumerate(row):
                table.cell(r, c).text = value
    doc.save(str(path))


def make_deck(root: Path, cards, source_kind="docx") -> Path:
    (root / "cards").mkdir(parents=True)
    (root / "deck.json").write_text(
        json.dumps({"name": "定位", "source_kind": source_kind}, ensure_ascii=False),
        encoding="utf-8")
    (root / "cards" / "01.json").write_text(
        json.dumps({"deck": "S", "cards": cards}, ensure_ascii=False),
        encoding="utf-8")
    return root


def qa(source=None, pages=None):
    card = {"type": "qa", "q": "q", "a": "a"}
    if source is not None:
        card["source"] = source
    if pages is not None:
        card["pages"] = pages
    return card


@unittest.skipUnless(HAS_DOCX, "需要 python-docx")
class DocxGateTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _ingest(self, paragraphs=("第一段", "第二段"), table_rows=(("A", "B"),)):
        path = self.tmp / "a.docx"
        make_docx(path, list(paragraphs), [list(r) for r in table_rows] if table_rows else None)
        out = ingest_mod.ingest_docx(path, out=self.tmp / "ing.json",
                                     repo_root=self.tmp).out_path
        return path, ingest_mod.load_ingest(out), out

    def test_valid_locators_pass(self):
        _path, data, _out = self._ingest()
        deck = make_deck(self.tmp / "deck", [qa("para:1"), qa("table:1/r1")])
        report = validate(load_spec(deck), locators=data.locators)
        self.assertTrue(report.ok, report.errors)

    def test_bad_locator_grammar_rejected(self):
        _path, data, _out = self._ingest()
        for bad in ("第1段", "para:0", "para:x", "table:1", "table:1/r0", "page:1"):
            deck = make_deck(self.tmp / f"deck-{bad.replace(':', '-')}", [qa(bad)])
            report = validate(load_spec(deck), locators=data.locators)
            self.assertFalse(report.ok, bad)
            self.assertTrue(any("定位格式非法" in e for e in report.errors), report.errors)

    def test_missing_source_rejected(self):
        _path, data, _out = self._ingest()
        deck = make_deck(self.tmp / "deck", [qa()])
        report = validate(load_spec(deck), locators=data.locators)
        self.assertTrue(any("source 必填" in e for e in report.errors), report.errors)

    def test_locator_not_in_ingest_rejected(self):
        _path, data, _out = self._ingest()
        deck = make_deck(self.tmp / "deck", [qa("para:99")])
        report = validate(load_spec(deck), locators=data.locators)
        self.assertTrue(any("不在 ingest 产物中" in e for e in report.errors), report.errors)

    def test_empty_locator_rejected(self):
        _path, data, _out = self._ingest(paragraphs=("有文本", ""))
        deck = make_deck(self.tmp / "deck", [qa("para:2")])
        report = validate(load_spec(deck), locators=data.locators)
        self.assertTrue(any("没有文本" in e for e in report.errors), report.errors)

    def test_pages_not_allowed_for_docx(self):
        _path, data, _out = self._ingest()
        deck = make_deck(self.tmp / "deck", [qa("para:1", pages=[1])])
        report = validate(load_spec(deck), locators=data.locators)
        self.assertTrue(any("不能用 pages" in e for e in report.errors), report.errors)

    def test_check_cli_valid(self):
        path, _data, out = self._ingest()
        deck = make_deck(self.tmp / "deck", [qa("para:1")])
        code, text = run(["check", str(deck), "--docx", str(path), "--ingest", str(out)])
        self.assertEqual(code, 0, text)
        self.assertIn("校验通过", text)

    def test_check_cli_bad_locator(self):
        path, _data, out = self._ingest()
        deck = make_deck(self.tmp / "deck", [qa("para:99")])
        code, text = run(["check", str(deck), "--docx", str(path), "--ingest", str(out)])
        self.assertEqual(code, 1, text)
        self.assertIn("不在 ingest 产物中", text)

    def test_pdf_and_docx_conflict(self):
        path, _data, out = self._ingest()
        deck = make_deck(self.tmp / "deck", [qa("para:1")])
        code, text = run(["check", str(deck), "--pdf", str(path),
                          "--docx", str(path), "--ingest", str(out)])
        self.assertEqual(code, 2, text)
        self.assertIn("只能给一个", text)

    def test_sha_mismatch(self):
        path, _data, out = self._ingest()
        deck = make_deck(self.tmp / "deck", [qa("para:1")])
        doc = docx.Document()
        doc.add_paragraph("改过的内容")
        doc.save(str(path))
        code, text = run(["check", str(deck), "--docx", str(path), "--ingest", str(out)])
        self.assertEqual(code, 2, text)
        self.assertIn("不是同一份文件", text)

    def test_missing_docx_path_reports_exit_2(self):
        _path, _data, out = self._ingest()
        deck = make_deck(self.tmp / "deck", [qa("para:1")])
        missing = self.tmp / "nope.docx"
        code, text = run(["check", str(deck), "--docx", str(missing), "--ingest", str(out)])
        self.assertEqual(code, 2, text)
        self.assertIn("找不到 DOCX", text)
        self.assertNotIn("Traceback", text)

    def test_docx_path_is_directory_reports_exit_2(self):
        _path, _data, out = self._ingest()
        deck = make_deck(self.tmp / "deck", [qa("para:1")])
        code, text = run(["check", str(deck), "--docx", str(self.tmp), "--ingest", str(out)])
        self.assertEqual(code, 2, text)
        self.assertIn("不是文件", text)
        self.assertNotIn("Traceback", text)

    def test_unknown_kind_with_docx_locator_requires_gate(self):
        _path, _data, _out = self._ingest()
        deck = make_deck(self.tmp / "deck", [qa("para:1")], source_kind="unknown")
        spec = load_spec(deck)
        from ankicards.cli import _require_gate
        with self.assertRaises(GateError):
            _require_gate(spec, None)

    def test_unknown_kind_locator_checked_when_ingest_given(self):
        _path, data, _out = self._ingest()
        deck = make_deck(self.tmp / "deck", [qa("para:99")], source_kind="unknown")
        report = validate(load_spec(deck), locators=data.locators)
        self.assertTrue(any("不在 ingest 产物中" in e for e in report.errors), report.errors)

    def test_unknown_kind_with_docx_locator_warns(self):
        _path, _data, _out = self._ingest()
        deck = make_deck(self.tmp / "deck", [qa("para:1")], source_kind="unknown")
        report = validate(load_spec(deck))
        self.assertTrue(any("未把 source_kind 设为 docx" in w for w in report.warnings),
                        report.warnings)

    def test_unknown_kind_build_cli_requires_ingest(self):
        path, _data, _out = self._ingest()
        deck = make_deck(self.tmp / "deck", [qa("para:1")], source_kind="unknown")
        code, text = run(["build", str(deck), "--out", str(self.tmp / "x.apkg"),
                          "--docx", str(path)])
        self.assertEqual(code, 1, text)
        self.assertIn("溯源闸门", text)

    def test_build_gate_requires_ingest(self):
        _path, _data, _out = self._ingest()
        deck = make_deck(self.tmp / "deck", [qa("para:1")])
        spec = load_spec(deck)
        from ankicards.cli import _require_gate
        with self.assertRaises(GateError):
            _require_gate(spec, None)


if __name__ == "__main__":
    unittest.main()
