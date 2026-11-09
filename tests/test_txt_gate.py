"""TXT 定位闸门：line:N 语法、ingest 存在性、build 闸门与 --txt 同源校验。"""

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from ankicards import ingest as ingest_mod
from ankicards.cli import main
from ankicards.schema import load_spec, validate


def run_cli(args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(args)
    return code, out.getvalue() + err.getvalue()


def make_deck(root: Path, source_kind: str = "txt", source: str | None = "line:2",
              pages: list[int] | None = None) -> Path:
    (root / "cards").mkdir(parents=True)
    (root / "deck.json").write_text(
        json.dumps({"name": "TXT 测试", "source_kind": source_kind}, ensure_ascii=False),
        encoding="utf-8")
    card = {"type": "qa", "q": "问题", "a": "答案"}
    if source is not None:
        card["source"] = source
    if pages is not None:
        card["pages"] = pages
    (root / "cards" / "01.json").write_text(
        json.dumps({"deck": "TXT", "cards": [card]}, ensure_ascii=False),
        encoding="utf-8")
    return root


def make_txt(tmp: Path, text: str = "一\n二\n三\n", name: str = "a.txt") -> Path:
    path = tmp / name
    path.write_text(text, encoding="utf-8")
    return path


class TxtValidateTest(unittest.TestCase):
    def test_valid_line_locator(self):
        with tempfile.TemporaryDirectory() as tmp:
            deck = make_deck(Path(tmp) / "deck", source="line:2")
            spec = load_spec(deck)
            report = validate(spec, locators={"line:2": "二"})
            self.assertTrue(report.ok, report.errors)

    def test_missing_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            deck = make_deck(Path(tmp) / "deck", source=None)
            report = validate(load_spec(deck), locators={"line:2": "二"})
            self.assertFalse(report.ok)
            self.assertTrue(any("source" in e for e in report.errors))

    def test_bad_locator_grammar(self):
        with tempfile.TemporaryDirectory() as tmp:
            for bad in ("line:0", "line:01", "page:2", "2", "line:2x"):
                deck = make_deck(Path(tmp) / f"deck-{bad}".replace(":", "_"),
                                 source=bad)
                report = validate(load_spec(deck), locators={"line:2": "二"})
                self.assertFalse(report.ok, bad)

    def test_locator_missing_from_ingest(self):
        with tempfile.TemporaryDirectory() as tmp:
            deck = make_deck(Path(tmp) / "deck", source="line:9")
            report = validate(load_spec(deck), locators={"line:2": "二"})
            self.assertFalse(report.ok)
            self.assertTrue(any("line:9" in e and "不在" in e for e in report.errors))

    def test_empty_locator_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            deck = make_deck(Path(tmp) / "deck", source="line:2")
            report = validate(load_spec(deck), locators={"line:2": "  "})
            self.assertFalse(report.ok)
            self.assertTrue(any("没有文本" in e for e in report.errors))

    def test_pages_not_allowed_for_txt(self):
        with tempfile.TemporaryDirectory() as tmp:
            deck = make_deck(Path(tmp) / "deck", source=None, pages=[1])
            report = validate(load_spec(deck))
            self.assertFalse(report.ok)
            self.assertTrue(any("pages" in e for e in report.errors))

    def test_unknown_kind_with_txt_locator_warns_and_checks(self):
        with tempfile.TemporaryDirectory() as tmp:
            deck = make_deck(Path(tmp) / "deck", source_kind="unknown", source="line:2")
            report = validate(load_spec(deck), locators={"line:2": "二"})
            self.assertTrue(report.ok, report.errors)
            self.assertTrue(any("TXT 定位" in w for w in report.warnings))


class TxtCliTest(unittest.TestCase):
    def _prepare(self, tmp: Path):
        txt = make_txt(tmp)
        manifest = ingest_mod.ingest_txt(
            txt, out=tmp / "ing.json", repo_root=tmp).out_path
        deck = make_deck(tmp / "deck")
        return txt, manifest, deck

    def test_check_with_txt_and_ingest_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            txt, manifest, deck = self._prepare(Path(tmp))
            code, output = run_cli(["check", str(deck), "--txt", str(txt),
                                    "--ingest", str(manifest)])
            self.assertEqual(code, 0, output)

    def test_build_without_ingest_is_gate_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, _, deck = self._prepare(Path(tmp))
            code, output = run_cli(["build", str(deck), "--out", str(Path(tmp) / "x.apkg")])
            self.assertEqual(code, 1, output)
            self.assertIn("闸门", output)

    def test_build_with_txt_and_ingest_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            txt, manifest, deck = self._prepare(Path(tmp))
            code, output = run_cli(["build", str(deck), "--out", str(Path(tmp) / "x.apkg"),
                                    "--txt", str(txt), "--ingest", str(manifest)])
            self.assertEqual(code, 0, output)

    def test_mismatched_txt_is_exit_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, manifest, deck = self._prepare(Path(tmp))
            other = make_txt(Path(tmp), "完全不同的内容\n", "other.txt")
            code, output = run_cli(["check", str(deck), "--txt", str(other),
                                    "--ingest", str(manifest)])
            self.assertEqual(code, 2, output)
            self.assertIn("不是同一份文件", output)

    def test_missing_txt_path_is_exit_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, manifest, deck = self._prepare(Path(tmp))
            code, output = run_cli(["check", str(deck), "--txt", str(Path(tmp) / "nope.txt"),
                                    "--ingest", str(manifest)])
            self.assertEqual(code, 2, output)

    def test_txt_and_pdf_are_mutually_exclusive(self):
        with tempfile.TemporaryDirectory() as tmp:
            txt, manifest, deck = self._prepare(Path(tmp))
            code, output = run_cli(["check", str(deck), "--txt", str(txt),
                                    "--pdf", str(Path(tmp) / "x.pdf"),
                                    "--ingest", str(manifest)])
            self.assertEqual(code, 2, output)
            self.assertIn("只能给一个", output)


if __name__ == "__main__":
    unittest.main()
