"""ingest 的回归测试：文本型 PDF 正常、异常输入拒绝、产物确定性。

CI 只安装 genanki，因此依赖 PyMuPDF / python-docx 的用例在缺失时跳过。
"""

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

try:
    import pymupdf  # type: ignore
    HAS_PYMUPDF = True
except ImportError:  # pragma: no cover
    HAS_PYMUPDF = False

try:
    import docx  # type: ignore
    HAS_DOCX = True
except ImportError:  # pragma: no cover
    HAS_DOCX = False

from ankicards.ingest import IngestError, ingest_pdf


def _text_pdf(path: Path, pages: int = 2) -> None:
    doc = pymupdf.open()
    for index in range(pages):
        page = doc.new_page()
        page.insert_text((72, 72), f"第 {index + 1} 页内容")
    doc.save(str(path))
    doc.close()


@unittest.skipUnless(HAS_PYMUPDF, "需要 PyMuPDF")
class IngestPdfTest(unittest.TestCase):
    def test_text_pdf_units(self):
        with tempfile.TemporaryDirectory() as tmp:
            pdf = Path(tmp) / "a.pdf"
            _text_pdf(pdf, pages=3)
            result = ingest_pdf(pdf, out=Path(tmp) / "out.json")
            manifest = result.manifest
            self.assertEqual(manifest["unit_count"], 3)
            self.assertEqual(manifest["unit_kind"], "page")
            self.assertEqual([u["id"] for u in manifest["units"]],
                             ["page:1", "page:2", "page:3"])
            self.assertGreater(manifest["total_chars"], 0)
            self.assertEqual(manifest["source"], "a.pdf")
            self.assertEqual(manifest["source_sha256"],
                             hashlib.sha256(pdf.read_bytes()).hexdigest())

    def test_output_is_deterministic(self):
        with tempfile.TemporaryDirectory() as tmp:
            pdf = Path(tmp) / "a.pdf"
            _text_pdf(pdf)
            one = Path(tmp) / "1.json"
            two = Path(tmp) / "2.json"
            ingest_pdf(pdf, out=one)
            ingest_pdf(pdf, out=two)
            self.assertEqual(one.read_bytes(), two.read_bytes())
            data = json.loads(one.read_text(encoding="utf-8"))
            self.assertEqual(data["source"], "a.pdf")
            self.assertNotIn(str(pdf), one.read_text(encoding="utf-8"))

    def test_rejects_image_only_pdf(self):
        with tempfile.TemporaryDirectory() as tmp:
            pdf = Path(tmp) / "blank.pdf"
            doc = pymupdf.open()
            doc.new_page()
            doc.save(str(pdf))
            doc.close()
            with self.assertRaises(IngestError) as ctx:
                ingest_pdf(pdf, out=Path(tmp) / "x.json")
            self.assertEqual(ctx.exception.code, 2)
            self.assertIn("OCR", str(ctx.exception))

    def test_rejects_encrypted_pdf(self):
        with tempfile.TemporaryDirectory() as tmp:
            pdf = Path(tmp) / "enc.pdf"
            doc = pymupdf.open()
            doc.new_page().insert_text((72, 72), "secret")
            doc.save(str(pdf), encryption=pymupdf.PDF_ENCRYPT_AES_256,
                     owner_pw="o", user_pw="u")
            doc.close()
            with self.assertRaises(IngestError) as ctx:
                ingest_pdf(pdf, out=Path(tmp) / "x.json")
            self.assertIn("加密", str(ctx.exception))

    def test_rejects_pdf_over_page_limit(self):
        with tempfile.TemporaryDirectory() as tmp:
            pdf = Path(tmp) / "a.pdf"
            _text_pdf(pdf, pages=3)
            with self.assertRaises(IngestError) as ctx:
                ingest_pdf(pdf, out=Path(tmp) / "x.json", max_pages=2)
            self.assertIn("上限", str(ctx.exception))

    def test_repaired_pdf_rejected_by_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            good = Path(tmp) / "good.pdf"
            _text_pdf(good, pages=3)
            data = good.read_bytes()
            idx = data.rfind(b"startxref")
            broken = Path(tmp) / "broken.pdf"
            broken.write_bytes(data[:idx] + b"startxref\n0\n%%EOF\n")
            with self.assertRaises(IngestError) as ctx:
                ingest_pdf(broken, out=Path(tmp) / "x.json")
            self.assertIn("修复", str(ctx.exception))

    def test_repaired_pdf_allowed_with_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            good = Path(tmp) / "good.pdf"
            _text_pdf(good, pages=3)
            data = good.read_bytes()
            idx = data.rfind(b"startxref")
            broken = Path(tmp) / "broken.pdf"
            broken.write_bytes(data[:idx] + b"startxref\n0\n%%EOF\n")
            result = ingest_pdf(broken, out=Path(tmp) / "x.json", allow_repaired=True)
            self.assertTrue(result.manifest["repaired"])
            self.assertTrue(any("修复" in w for w in result.manifest["warnings"]))

    def test_half_empty_pages_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            pdf = Path(tmp) / "half.pdf"
            doc = pymupdf.open()
            for index in range(10):
                page = doc.new_page()
                if index < 5:
                    page.insert_text((72, 72), f"第 {index + 1} 页")
            doc.save(str(pdf))
            doc.close()
            with self.assertRaises(IngestError) as ctx:
                ingest_pdf(pdf, out=Path(tmp) / "x.json")
            self.assertEqual(ctx.exception.code, 2)
            self.assertIn("50%", str(ctx.exception))

    def test_exactly_twenty_percent_warns(self):
        with tempfile.TemporaryDirectory() as tmp:
            pdf = Path(tmp) / "fifth.pdf"
            doc = pymupdf.open()
            for index in range(10):
                page = doc.new_page()
                if index < 8:
                    page.insert_text((72, 72), f"第 {index + 1} 页")
            doc.save(str(pdf))
            doc.close()
            result = ingest_pdf(pdf, out=Path(tmp) / "x.json")
            self.assertEqual(len(result.manifest["empty_pages"]), 2)
            self.assertTrue(any("没有文本" in w for w in result.manifest["warnings"]))

    def test_moderate_empty_pages_warn_but_succeed(self):
        with tempfile.TemporaryDirectory() as tmp:
            pdf = Path(tmp) / "mixed.pdf"
            doc = pymupdf.open()
            for index in range(10):
                page = doc.new_page()
                if index < 7:
                    page.insert_text((72, 72), f"第 {index + 1} 页")
            doc.save(str(pdf))
            doc.close()
            result = ingest_pdf(pdf, out=Path(tmp) / "x.json")
            self.assertEqual(result.manifest["unit_count"], 10)
            self.assertEqual(len(result.manifest["empty_pages"]), 3)
            self.assertTrue(any("没有文本" in w for w in result.manifest["warnings"]))

    def test_out_outside_repo_is_allowed(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            other = Path(tmp) / "elsewhere"
            repo.mkdir()
            other.mkdir()
            pdf = repo / "a.pdf"
            _text_pdf(pdf)
            result = ingest_pdf(pdf, out=other / "x.json", repo_root=repo)
            self.assertTrue(result.out_path.exists())

    def test_rejects_out_inside_cards(self):
        with tempfile.TemporaryDirectory() as tmp:
            pdf = Path(tmp) / "a.pdf"
            _text_pdf(pdf)
            with self.assertRaises(IngestError):
                ingest_pdf(pdf, out=Path(tmp) / "deck" / "cards" / "x.json",
                           repo_root=Path(tmp))


class IngestRejectTest(unittest.TestCase):
    def test_rejects_markdown(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "a.md"
            path.write_text("# x", encoding="utf-8")
            with self.assertRaises(IngestError) as ctx:
                ingest_pdf(path)
            self.assertIn("import", str(ctx.exception))

    @unittest.skipUnless(HAS_DOCX, "需要 python-docx")
    def test_rejects_docx(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "a.docx"
            docx.Document().save(str(path))
            with self.assertRaises(IngestError) as ctx:
                ingest_pdf(path)
            self.assertIn("不是 PDF", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
