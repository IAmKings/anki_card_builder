"""ingest 与 PDF 的同源绑定：sha256 不一致必须拒绝，缺 sha 时警告放行。"""

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from ankicards import ingest as ingest_mod
from ankicards.cli import main

try:
    import pymupdf  # type: ignore
    HAS_PYMUPDF = True
except ImportError:  # pragma: no cover
    HAS_PYMUPDF = False


def run(args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(args)
    return code, out.getvalue() + err.getvalue()


def make_pdf(path: Path, text: str) -> None:
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    doc.save(str(path))
    doc.close()


def make_deck(root: Path) -> Path:
    (root / "cards").mkdir(parents=True)
    (root / "deck.json").write_text(
        json.dumps({"name": "同源", "source_kind": "pdf"}, ensure_ascii=False), encoding="utf-8")
    (root / "cards" / "01.json").write_text(
        json.dumps({"deck": "S", "cards": [
            {"type": "qa", "q": "q", "a": "a", "pages": [1]}]}, ensure_ascii=False),
        encoding="utf-8")
    return root


@unittest.skipUnless(HAS_PYMUPDF, "需要 PyMuPDF")
class IngestBindingTest(unittest.TestCase):
    def _prepare(self, tmp: Path):
        pdf = tmp / "a.pdf"
        make_pdf(pdf, "page one text")
        manifest = ingest_mod.ingest_pdf(pdf, out=tmp / "ing.json", repo_root=tmp).out_path
        deck = make_deck(tmp / "deck")
        return pdf, manifest, deck

    def test_load_ingest_exposes_sha_and_pages(self):
        with tempfile.TemporaryDirectory() as tmp:
            pdf, manifest, _ = self._prepare(Path(tmp))
            data = ingest_mod.load_ingest(manifest)
            self.assertEqual(data.source_sha256, ingest_mod.file_sha256(pdf))
            self.assertIn("page one text", data.pages[1])

    def test_mismatched_pdf_is_exit_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, manifest, deck = self._prepare(Path(tmp))
            other = Path(tmp) / "b.pdf"
            make_pdf(other, "完全不同的内容")
            code, output = run(["check", str(deck), "--pdf", str(other),
                                "--ingest", str(manifest)])
            self.assertEqual(code, 2, output)
            self.assertIn("不是同一份文件", output)

    def test_matching_pdf_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            pdf, manifest, deck = self._prepare(Path(tmp))
            code, output = run(["check", str(deck), "--pdf", str(pdf),
                                "--ingest", str(manifest)])
            self.assertEqual(code, 0, output)

    def test_manifest_without_sha_warns_but_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            pdf, _, deck = self._prepare(Path(tmp))
            legacy = Path(tmp) / "legacy.json"
            legacy.write_text(json.dumps({"format": "pdf", "units": [
                {"id": "page:1", "page": 1, "chars": 1, "text": "x"}]},
                ensure_ascii=False), encoding="utf-8")
            code, output = run(["check", str(deck), "--pdf", str(pdf),
                                "--ingest", str(legacy)])
            self.assertEqual(code, 0, output)
            self.assertIn("跳过同源校验", output)


if __name__ == "__main__":
    unittest.main()
