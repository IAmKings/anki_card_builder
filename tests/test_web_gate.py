"""Web 定位闸门：block:N 语法、ingest 存在性、build 闸门与 --html 同源校验。"""

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from ankicards import ingest as ingest_mod
from ankicards.cli import main
from ankicards.schema import load_spec, validate

HTML = "<html><body><h1>标题</h1><p>正文</p><p>2. **UDP**：无连接</p></body></html>"


def run_cli(args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(args)
    return code, out.getvalue() + err.getvalue()


def make_deck(root: Path, source_kind: str = "web", source: str | None = "block:1",
              pages: list[int] | None = None) -> Path:
    (root / "cards").mkdir(parents=True)
    (root / "deck.json").write_text(
        json.dumps({"name": "Web 测试", "source_kind": source_kind}, ensure_ascii=False),
        encoding="utf-8")
    card = {"type": "qa", "q": "问题", "a": "答案"}
    if source is not None:
        card["source"] = source
    if pages is not None:
        card["pages"] = pages
    (root / "cards" / "01.json").write_text(
        json.dumps({"deck": "Web", "cards": [card]}, ensure_ascii=False),
        encoding="utf-8")
    return root


def make_html(tmp: Path, name: str = "page.html") -> Path:
    path = tmp / name
    path.write_text(HTML, encoding="utf-8")
    return path


class WebValidateTest(unittest.TestCase):
    def test_valid_block_locator(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec = load_spec(make_deck(Path(tmp) / "deck"))
            report = validate(spec, locators={"block:1": "标题"})
            self.assertTrue(report.ok, report.errors)

    def test_missing_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec = load_spec(make_deck(Path(tmp) / "deck", source=None))
            report = validate(spec, locators={"block:1": "标题"})
            self.assertFalse(report.ok)
            self.assertTrue(any("source" in e for e in report.errors))

    def test_bad_locator_grammar(self):
        with tempfile.TemporaryDirectory() as tmp:
            for bad in ("block:0", "block:01", "page:1", "1", "block:1x"):
                spec = load_spec(make_deck(Path(tmp) / f"d-{bad}".replace(":", "_"),
                                           source=bad))
                report = validate(spec, locators={"block:1": "标题"})
                self.assertFalse(report.ok, bad)

    def test_locator_missing_from_ingest(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec = load_spec(make_deck(Path(tmp) / "deck", source="block:9"))
            report = validate(spec, locators={"block:1": "标题"})
            self.assertFalse(report.ok)
            self.assertTrue(any("block:9" in e and "不在" in e for e in report.errors))

    def test_empty_locator_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec = load_spec(make_deck(Path(tmp) / "deck"))
            report = validate(spec, locators={"block:1": "  "})
            self.assertFalse(report.ok)
            self.assertTrue(any("没有文本" in e for e in report.errors))

    def test_pages_not_allowed_for_web(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec = load_spec(make_deck(Path(tmp) / "deck", source=None, pages=[1]))
            report = validate(spec)
            self.assertFalse(report.ok)
            self.assertTrue(any("pages" in e for e in report.errors))

    def test_unknown_kind_with_web_locator_warns_and_checks(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec = load_spec(make_deck(Path(tmp) / "deck", source_kind="unknown"))
            report = validate(spec, locators={"block:1": "标题"})
            self.assertTrue(report.ok, report.errors)
            self.assertTrue(any("WEB 定位" in w or "Web 定位" in w for w in report.warnings))


class WebCliTest(unittest.TestCase):
    def _prepare(self, tmp: Path):
        html = make_html(tmp)
        manifest = ingest_mod.ingest_html(
            html, out=tmp / "ing.json", repo_root=tmp).out_path
        deck = make_deck(tmp / "deck")
        return html, manifest, deck

    def test_check_with_html_and_ingest_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            html, manifest, deck = self._prepare(Path(tmp))
            code, output = run_cli(["check", str(deck), "--html", str(html),
                                    "--ingest", str(manifest)])
            self.assertEqual(code, 0, output)

    def test_build_without_ingest_is_gate_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, _, deck = self._prepare(Path(tmp))
            code, output = run_cli(["build", str(deck), "--out", str(Path(tmp) / "x.apkg")])
            self.assertEqual(code, 1, output)
            self.assertIn("闸门", output)

    def test_build_with_html_and_ingest_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            html, manifest, deck = self._prepare(Path(tmp))
            code, output = run_cli(["build", str(deck), "--out", str(Path(tmp) / "x.apkg"),
                                    "--html", str(html), "--ingest", str(manifest)])
            self.assertEqual(code, 0, output)

    def test_url_style_deck_builds_with_ingest_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            html, manifest, deck = self._prepare(Path(tmp))
            code, output = run_cli(["build", str(deck), "--out", str(Path(tmp) / "x.apkg"),
                                    "--ingest", str(manifest)])
            self.assertEqual(code, 0, output)

    def test_mismatched_html_is_exit_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, manifest, deck = self._prepare(Path(tmp))
            other = make_html(Path(tmp), "other.html")
            other.write_text("<body><p>不同</p></body>", encoding="utf-8")
            code, output = run_cli(["check", str(deck), "--html", str(other),
                                    "--ingest", str(manifest)])
            self.assertEqual(code, 2, output)
            self.assertIn("不是同一份文件", output)

    def test_missing_html_path_is_exit_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, manifest, deck = self._prepare(Path(tmp))
            code, output = run_cli(["check", str(deck), "--html", str(Path(tmp) / "nope.html"),
                                    "--ingest", str(manifest)])
            self.assertEqual(code, 2, output)

    def test_html_and_txt_are_mutually_exclusive(self):
        with tempfile.TemporaryDirectory() as tmp:
            html, manifest, deck = self._prepare(Path(tmp))
            txt = Path(tmp) / "a.txt"
            txt.write_text("1. **X**：Y\n", encoding="utf-8")
            code, output = run_cli(["check", str(deck), "--html", str(html),
                                    "--txt", str(txt), "--ingest", str(manifest)])
            self.assertEqual(code, 2, output)
            self.assertIn("只能给一个", output)


if __name__ == "__main__":
    unittest.main()
