"""docx-points 适配器：标题分段 + 编号点/表格行，source 必须与 ingest 定位一致。"""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

try:
    import docx  # type: ignore
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    HAS_DOCX = True
except ImportError:  # pragma: no cover
    HAS_DOCX = False

from ankicards import ingest as ingest_mod
from ankicards.adapters import ADAPTERS, write_deck
from ankicards.errors import CardError
from ankicards.schema import load_spec, validate


def make_docx(path: Path) -> None:
    doc = docx.Document()
    doc.add_heading("第一章", level=1)
    doc.add_paragraph("1. **概念**：解释一")
    doc.add_paragraph("2. 机制：解释二")
    table = doc.add_table(rows=3, cols=2)
    for r, row in enumerate([["概念", "解释"], ["甲", "说明甲"], ["乙", "说明乙"]]):
        for c, value in enumerate(row):
            table.cell(r, c).text = value
    doc.save(str(path))


def add_auto_numbering(paragraph) -> None:
    """给段落加 w:numPr，模拟 Word 自动编号（python-docx 的 text 不含编号）。"""
    pPr = paragraph._p.get_or_add_pPr()
    numPr = OxmlElement("w:numPr")
    ilvl = OxmlElement("w:ilvl")
    ilvl.set(qn("w:val"), "0")
    num_id = OxmlElement("w:numId")
    num_id.set(qn("w:val"), "1")
    numPr.append(ilvl)
    numPr.append(num_id)
    pPr.append(numPr)


@unittest.skipUnless(HAS_DOCX, "需要 python-docx")
class DocxPointsAdapterTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.path = self.tmp / "notes.docx"
        make_docx(self.path)

    def tearDown(self):
        self._tmp.cleanup()

    def _deck(self):
        return ADAPTERS["docx-points"](self.path, name="测试")

    def test_sections_and_cards(self):
        deck = self._deck()
        self.assertEqual(deck.source_kind, "docx")
        self.assertEqual(list(deck.sections), ["第一章"])
        cards = deck.sections["第一章"]
        self.assertEqual(len(cards), 4)
        self.assertEqual([c["source"] for c in cards],
                         ["para:2", "para:3", "table:1/r2", "table:1/r3"])
        self.assertEqual(cards[0]["q"], "什么是概念？")
        self.assertEqual(cards[0]["a"], "解释一")
        self.assertEqual(cards[1]["q"], "什么是机制？")
        self.assertEqual(cards[2]["q"], "甲")
        self.assertEqual(cards[2]["a"], "说明甲")
        self.assertTrue(all(c["type"] == "qa" for c in cards))

    def test_table_duplicate_cells_collapsed(self):
        path = self.tmp / "dup.docx"
        doc = docx.Document()
        doc.add_heading("表格", level=1)
        table = doc.add_table(rows=2, cols=3)
        for r, row in enumerate([["甲", "甲", "乙"], ["丙", "", "丁"]]):
            for c, value in enumerate(row):
                table.cell(r, c).text = value
        doc.save(str(path))

        deck = ADAPTERS["docx-points"](path)
        cards = deck.sections["表格"]
        self.assertEqual([c["source"] for c in cards], ["table:1/r1", "table:1/r2"])
        self.assertEqual((cards[0]["q"], cards[0]["a"]), ("甲", "乙"))
        self.assertEqual((cards[1]["q"], cards[1]["a"]), ("丙", "丁"))

        result = ingest_mod.ingest_docx(path, out=self.tmp / "dup.json",
                                        repo_root=self.tmp)
        data = ingest_mod.load_ingest(result.out_path)
        self.assertTrue(all(c["source"] in data.locators for c in cards))

    def test_table_first_row_data_not_dropped(self):
        path = self.tmp / "data.docx"
        doc = docx.Document()
        doc.add_heading("数据", level=1)
        table = doc.add_table(rows=2, cols=2)
        for r, row in enumerate([["端口", "解释"], ["8080", "服务"]]):
            for c, value in enumerate(row):
                table.cell(r, c).text = value
        doc.save(str(path))

        cards = ADAPTERS["docx-points"](path).sections["数据"]
        self.assertEqual([c["source"] for c in cards], ["table:1/r1", "table:1/r2"])
        self.assertEqual((cards[0]["q"], cards[0]["a"]), ("端口", "解释"))

    def test_corrupt_docx_rejected(self):
        path = self.tmp / "bad.docx"
        path.write_bytes(b"not a zip")
        with self.assertRaises(CardError) as ctx:
            ADAPTERS["docx-points"](path)
        self.assertIn("无法打开 DOCX", str(ctx.exception))

    def test_memory_error_not_wrapped(self):
        with mock.patch("docx.Document", side_effect=MemoryError):
            with self.assertRaises(MemoryError):
                ADAPTERS["docx-points"](self.path)

    def test_auto_numbering_without_manual_numbers_has_hint(self):
        path = self.tmp / "auto.docx"
        doc = docx.Document()
        doc.add_heading("第一章", level=1)
        add_auto_numbering(doc.add_paragraph("自动编号的知识点"))
        doc.save(str(path))

        with self.assertRaises(CardError) as ctx:
            ADAPTERS["docx-points"](path)
        self.assertIn("Word 自动编号", str(ctx.exception))
        self.assertIn("手写编号", str(ctx.exception))

    def test_auto_numbering_warns_when_other_cards_exist(self):
        path = self.tmp / "mixed.docx"
        doc = docx.Document()
        doc.add_heading("第一章", level=1)
        add_auto_numbering(doc.add_paragraph("自动编号的知识点"))
        doc.add_paragraph("1. **概念**：解释")
        doc.save(str(path))

        deck = ADAPTERS["docx-points"](path)
        self.assertEqual(deck.card_count, 1)
        self.assertTrue(any("Word 自动编号" in w for w in deck.warnings), deck.warnings)

    def test_cli_import_prints_auto_numbering_warning(self):
        import contextlib
        import io
        from ankicards.cli import main

        path = self.tmp / "mixed.docx"
        doc = docx.Document()
        doc.add_heading("第一章", level=1)
        add_auto_numbering(doc.add_paragraph("自动编号的知识点"))
        doc.add_paragraph("1. **概念**：解释")
        doc.save(str(path))

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            code = main(["import", str(path), "--adapter", "docx-points",
                         "--out", str(self.tmp / "deck")])
        self.assertEqual(code, 0, buf.getvalue())
        self.assertIn("Word 自动编号", buf.getvalue())

    def test_sources_match_ingest_locators(self):
        result = ingest_mod.ingest_docx(self.path, out=self.tmp / "ing.json",
                                        repo_root=self.tmp)
        data = ingest_mod.load_ingest(result.out_path)
        deck = self._deck()
        write_deck(deck, self.tmp / "deck")
        report = validate(load_spec(self.tmp / "deck"), locators=data.locators)
        self.assertTrue(report.ok, report.errors)

    def test_cli_import_then_check(self):
        import contextlib
        import io
        from ankicards.cli import main

        out = self.tmp / "deck"
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            code = main(["import", str(self.path), "--adapter", "docx-points",
                         "--out", str(out)])
            self.assertEqual(code, 0, buf.getvalue())
            result = ingest_mod.ingest_docx(self.path, out=self.tmp / "ing.json",
                                            repo_root=self.tmp)
            code = main(["check", str(out), "--docx", str(self.path),
                         "--ingest", str(result.out_path)])
            self.assertEqual(code, 0, buf.getvalue())

    def test_cli_import_with_ingest_merges_continuation(self):
        import contextlib
        import io
        import json
        from ankicards.cli import main

        doc = docx.Document()
        doc.add_heading("第一章", level=1)
        doc.add_paragraph("1. **启动**：执行命令，默认端口 8080；")
        doc.add_paragraph("生产环境需覆盖配置并开启 TLS。")
        path = self.tmp / "cont.docx"
        doc.save(str(path))
        manifest = ingest_mod.ingest_docx(
            path, out=self.tmp / "ing2.json", repo_root=self.tmp).out_path

        out = self.tmp / "deck2"
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            code = main(["import", str(path), "--adapter", "docx-points",
                         "--ingest", str(manifest), "--out", str(out)])
        self.assertEqual(code, 0, buf.getvalue())
        cards = json.loads((out / "cards" / "01.json").read_text(encoding="utf-8"))["cards"]
        self.assertEqual(len(cards), 1, cards)
        self.assertEqual(cards[0]["source"], "para:2-3")
        self.assertIn("生产环境需覆盖配置并开启 TLS。", cards[0]["a"])

    def test_no_points_rejected(self):
        path = self.tmp / "plain.docx"
        doc = docx.Document()
        doc.add_paragraph("只有普通段落")
        doc.save(str(path))
        with self.assertRaises(CardError) as ctx:
            ADAPTERS["docx-points"](path)
        self.assertIn("没有解析出", str(ctx.exception))

    def test_non_docx_rejected(self):
        path = self.tmp / "a.txt"
        path.write_text("x", encoding="utf-8")
        with self.assertRaises(CardError) as ctx:
            ADAPTERS["docx-points"](path)
        self.assertIn(".docx", str(ctx.exception))

    def test_directory_rejected(self):
        with self.assertRaises(CardError) as ctx:
            ADAPTERS["docx-points"](self.tmp)
        self.assertIn("单个 .docx", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
