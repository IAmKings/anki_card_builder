"""CLI 错误路径与闸门的回归：退出码 2 / 1，且不得出现 traceback。"""

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from ankicards.cli import main

try:
    import pymupdf  # type: ignore
    HAS_PYMUPDF = True
except ImportError:  # pragma: no cover
    HAS_PYMUPDF = False


def _text_pdf(path: Path) -> None:
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), "第一页文本")
    doc.save(str(path))
    doc.close()


def _deck(tmp: Path, cards, kind="pdf") -> Path:
    root = tmp / "deck"
    (root / "cards").mkdir(parents=True)
    (root / "cards" / "01.json").write_text(
        json.dumps({"deck": "S", "cards": cards}, ensure_ascii=False), encoding="utf-8")
    (root / "deck.json").write_text(
        json.dumps({"name": "CLI", "source_kind": kind}, ensure_ascii=False), encoding="utf-8")
    return root


@unittest.skipUnless(HAS_PYMUPDF, "需要 PyMuPDF")
class CliErrorTest(unittest.TestCase):
    def test_missing_out_is_exit_2_without_traceback(self):
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            code = main(["import", "data/Android", "--adapter", "android-md"])
        self.assertEqual(code, 2)
        self.assertNotIn("Traceback", stderr.getvalue())

    def test_missing_source_is_exit_2(self):
        with contextlib.redirect_stderr(io.StringIO()):
            code = main(["import", "--adapter", "android-md", "--out", "/tmp/x"])
        self.assertEqual(code, 2)

    def test_bad_ingest_json_is_exit_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "bad.json"
            bad.write_text("{bad", encoding="utf-8")
            deck = _deck(Path(tmp), [{"type": "qa", "q": "q", "a": "a", "pages": [1]}])
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                code = main(["check", str(deck), "--ingest", str(bad)])
            self.assertEqual(code, 2)
            self.assertNotIn("Traceback", stderr.getvalue())

    def test_encrypted_pdf_check_is_exit_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            pdf = Path(tmp) / "enc.pdf"
            doc = pymupdf.open()
            doc.new_page().insert_text((72, 72), "secret")
            doc.save(str(pdf), encryption=pymupdf.PDF_ENCRYPT_AES_256,
                     owner_pw="o", user_pw="u")
            doc.close()
            deck = _deck(Path(tmp), [{"type": "qa", "q": "q", "a": "a", "pages": [1]}])
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                code = main(["check", str(deck), "--pdf", str(pdf)])
            self.assertEqual(code, 2)
            self.assertNotIn("Traceback", stderr.getvalue())

    def test_missing_apkg_verify_is_exit_2(self):
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            code = main(["verify", "/tmp/definitely-not-there.apkg"])
        self.assertEqual(code, 2)
        self.assertNotIn("Traceback", stderr.getvalue())


@unittest.skipUnless(HAS_PYMUPDF, "需要 PyMuPDF")
class GateCliTest(unittest.TestCase):
    def _prepare(self, tmp: Path):
        pdf = tmp / "a.pdf"
        _text_pdf(pdf)
        deck = _deck(tmp, [{"type": "qa", "q": "问", "a": "答", "pages": [1]}])
        from ankicards.ingest import ingest_pdf

        result = ingest_pdf(pdf, out=tmp / "ingest.json", repo_root=tmp)
        return deck, pdf, result.out_path

    def test_build_with_pages_requires_ingest(self):
        with tempfile.TemporaryDirectory() as tmp:
            deck, pdf, _ = self._prepare(Path(tmp))
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                code = main(["build", str(deck), "--out", str(Path(tmp) / "x.apkg"),
                             "--pdf", str(pdf)])
            self.assertEqual(code, 1)
            self.assertIn("--ingest", stderr.getvalue())

    def test_build_with_ingest_succeeds(self):
        with tempfile.TemporaryDirectory() as tmp:
            deck, pdf, manifest = self._prepare(Path(tmp))
            out = Path(tmp) / "x.apkg"
            code = main(["build", str(deck), "--out", str(out), "--pdf", str(pdf),
                         "--ingest", str(manifest)])
            self.assertEqual(code, 0)
            self.assertTrue(out.exists())

    def test_preview_without_ingest_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            deck, pdf, _ = self._prepare(Path(tmp))
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                code = main(["preview", str(deck), "--out", str(Path(tmp) / "p.html"),
                             "--pdf", str(pdf)])
            self.assertEqual(code, 1)
            self.assertIn("--ingest", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
