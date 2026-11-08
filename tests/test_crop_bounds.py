"""裁图尺寸校验回归：check 必须按被裁页的尺寸判断，build 不得抛 PyMuPDF 底层异常。"""

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from ankicards.cli import main
from ankicards.ingest import ingest_pdf

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


@unittest.skipUnless(HAS_PYMUPDF, "需要 PyMuPDF")
class CropBoundsTest(unittest.TestCase):
    def _prepare(self, tmp: Path, rect):
        pdf = tmp / "s.pdf"
        doc = pymupdf.open()
        page1 = doc.new_page(width=600, height=600)
        page1.insert_text((72, 72), "第一页")
        page2 = doc.new_page(width=100, height=100)
        page2.insert_text((10, 10), "第二页")
        doc.save(str(pdf))
        doc.close()

        deck = tmp / "deck"
        (deck / "cards").mkdir(parents=True)
        (deck / "cards" / "01.json").write_text(json.dumps({"deck": "S", "cards": [
            {"type": "image", "q": "q", "a": "a", "img": "c", "pages": [2]}]},
            ensure_ascii=False), encoding="utf-8")
        (deck / "crops.json").write_text(json.dumps(
            [{"name": "c", "page": 2, "rect": rect}], ensure_ascii=False), encoding="utf-8")
        (deck / "deck.json").write_text(json.dumps(
            {"name": "裁图", "source_kind": "pdf"}, ensure_ascii=False), encoding="utf-8")

        manifest = ingest_pdf(pdf, out=tmp / "ing.json", repo_root=tmp).out_path
        return deck, pdf, manifest

    def test_crop_outside_its_page_fails_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            deck, pdf, manifest = self._prepare(Path(tmp), [200, 200, 300, 300])
            code, output = run(["check", str(deck), "--pdf", str(pdf),
                                "--ingest", str(manifest)])
            self.assertEqual(code, 1, output)
            self.assertIn("第 2 页", output)

    def test_build_does_not_raise_mupdf_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            deck, pdf, manifest = self._prepare(Path(tmp), [200, 200, 300, 300])
            code, output = run(["build", str(deck), "--pdf", str(pdf),
                                "--ingest", str(manifest), "--out", str(Path(tmp) / "x.apkg")])
            # 数据错误由 validate 拦下 -> 1（不是 2），但绝不能抛 PyMuPDF 异常
            self.assertEqual(code, 1, output)
            self.assertNotIn("Traceback", output)
            self.assertNotIn("FzErrorLibrary", output)

    def test_crop_inside_page_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            deck, pdf, manifest = self._prepare(Path(tmp), [10, 10, 50, 50])
            code, output = run(["check", str(deck), "--pdf", str(pdf),
                                "--ingest", str(manifest)])
            self.assertEqual(code, 0, output)
            code, output = run(["build", str(deck), "--pdf", str(pdf),
                                "--ingest", str(manifest), "--out", str(Path(tmp) / "x.apkg")])
            self.assertEqual(code, 0, output)


if __name__ == "__main__":
    unittest.main()
