"""DOCX 文本摄取：段落/表格行定位、确定性、限制与拒收。

定位语法：
- para:N         body 内第 N 个 w:p（1 基；空段落也计数；表格内段落不计）
- table:T/rR     第 T 个 w:tbl 的第 R 行（1 基）
"""

import hashlib
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

try:
    import docx  # type: ignore
    HAS_DOCX = True
except ImportError:  # pragma: no cover
    HAS_DOCX = False

from ankicards import ingest as ingest_mod


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


@unittest.skipUnless(HAS_DOCX, "需要 python-docx")
class IngestDocxTest(unittest.TestCase):
    def test_paragraphs_and_table_rows_have_locators(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "a.docx"
            make_docx(path, ["第一段", "第二段"], [["A", "B"], ["C", "D"]])
            result = ingest_mod.ingest_docx(path, out=Path(tmp) / "out.json",
                                            repo_root=Path(tmp))
            manifest = result.manifest
            self.assertEqual(manifest["format"], "docx")
            self.assertEqual(manifest["unit_kind"], "block")
            self.assertEqual([u["id"] for u in manifest["units"]],
                             ["para:1", "para:2", "table:1/r1", "table:1/r2"])
            self.assertEqual(manifest["units"][2]["text"], "A | B")
            self.assertEqual(manifest["units"][3]["text"], "C | D")
            self.assertEqual(manifest["source_sha256"],
                             hashlib.sha256(path.read_bytes()).hexdigest())

    def test_output_is_deterministic_and_relative(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "a.docx"
            make_docx(path, ["一", "二"])
            one = Path(tmp) / "1.json"
            two = Path(tmp) / "2.json"
            ingest_mod.ingest_docx(path, out=one, repo_root=Path(tmp))
            ingest_mod.ingest_docx(path, out=two, repo_root=Path(tmp))
            self.assertEqual(one.read_bytes(), two.read_bytes())
            text = one.read_text(encoding="utf-8")
            self.assertEqual(json.loads(text)["source"], "a.docx")
            self.assertNotIn(str(path), text)

    def test_table_row_collapses_adjacent_duplicates(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "a.docx"
            make_docx(path, ["段"], [["A", "A", "B"]])
            manifest = ingest_mod.ingest_docx(
                path, out=Path(tmp) / "out.json", repo_root=Path(tmp)).manifest
            self.assertEqual(manifest["units"][1]["text"], "A | B")

    def test_empty_docx_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "empty.docx"
            docx.Document().save(str(path))
            with self.assertRaises(ingest_mod.IngestError) as ctx:
                ingest_mod.ingest_docx(path, out=Path(tmp) / "out.json")
            self.assertEqual(ctx.exception.code, 2)
            self.assertIn("没有可提取文本", str(ctx.exception))

    def test_corrupt_docx_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.docx"
            path.write_bytes(b"not a zip")
            with self.assertRaises(ingest_mod.IngestError) as ctx:
                ingest_mod.ingest_docx(path, out=Path(tmp) / "out.json")
            self.assertEqual(ctx.exception.code, 2)
            self.assertIn("DOCX", str(ctx.exception))

    def test_zip_uncompressed_size_cap(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "a.docx"
            make_docx(path, ["一"])
            with mock.patch.object(ingest_mod, "MAX_DOCX_UNCOMPRESSED_BYTES", 100):
                with self.assertRaises(ingest_mod.IngestError) as ctx:
                    ingest_mod.ingest_docx(path, out=Path(tmp) / "out.json")
            self.assertEqual(ctx.exception.code, 2)
            self.assertIn("解压后", str(ctx.exception))

    def test_encrypted_like_docx_rejected_as_ingest_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "encrypted.docx"
            path.write_bytes(bytes.fromhex("d0cf11e0a1b11ae1") + b"\0" * 512)
            with self.assertRaises(ingest_mod.IngestError) as ctx:
                ingest_mod.ingest_docx(path, out=Path(tmp) / "out.json")
            self.assertEqual(ctx.exception.code, 2)
            self.assertIn("损坏或已加密", str(ctx.exception))

    def test_zip_without_docx_package_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "fake.docx"
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("hello.txt", "x")
            with self.assertRaises(ingest_mod.IngestError) as ctx:
                ingest_mod.ingest_docx(path, out=Path(tmp) / "out.json")
            self.assertEqual(ctx.exception.code, 2)
            self.assertIn("无法打开 DOCX", str(ctx.exception))

    def test_memory_error_not_wrapped(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "a.docx"
            make_docx(path, ["一"])
            with mock.patch("docx.Document", side_effect=MemoryError):
                with self.assertRaises(MemoryError):
                    ingest_mod.ingest_docx(path, out=Path(tmp) / "out.json")

    def test_max_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "a.docx"
            make_docx(path, ["一", "二", "三"])
            with self.assertRaises(ingest_mod.IngestError) as ctx:
                ingest_mod.ingest_docx(path, out=Path(tmp) / "out.json",
                                       max_blocks=2)
            self.assertIn("上限", str(ctx.exception))

    def test_empty_units_warn_then_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            warn_path = Path(tmp) / "warn.docx"
            make_docx(warn_path, ["一", "二", "三", "四", "五", "六", "七", "八", "", ""])
            result = ingest_mod.ingest_docx(warn_path, out=Path(tmp) / "w.json",
                                            repo_root=Path(tmp))
            self.assertEqual(len(result.manifest["empty_units"]), 2)
            self.assertTrue(any("没有文本" in w for w in result.manifest["warnings"]))

            fail_path = Path(tmp) / "fail.docx"
            make_docx(fail_path, ["一", "二", "三", "四", "五", "", "", "", "", ""])
            with self.assertRaises(ingest_mod.IngestError) as ctx:
                ingest_mod.ingest_docx(fail_path, out=Path(tmp) / "f.json")
            self.assertIn("50%", str(ctx.exception))

    def test_doc_extension_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "a.doc"
            path.write_bytes(b"x")
            with self.assertRaises(ingest_mod.IngestError) as ctx:
                ingest_mod.ingest(path)
            self.assertIn(".docx", str(ctx.exception))

    def test_ingest_pdf_rejects_docx_with_hint(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "a.docx"
            make_docx(path, ["一"])
            with self.assertRaises(ingest_mod.IngestError) as ctx:
                ingest_mod.ingest_pdf(path)
            self.assertIn("不是 PDF", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
