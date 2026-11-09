"""DOCX 共享遍历：ingest 与 adapter 使用同一套段落/表格定位计数。"""

import unittest

try:
    import docx  # type: ignore
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    HAS_DOCX = True
except ImportError:  # pragma: no cover
    HAS_DOCX = False

from ankicards.docx import iter_docx_blocks


def add_auto_numbering(paragraph) -> None:
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
class DocxBlocksTest(unittest.TestCase):
    def setUp(self):
        doc = docx.Document()
        doc.add_heading("第一章", level=1)
        doc.add_paragraph("")
        doc.add_paragraph("1. **概念**：解释")
        table = doc.add_table(rows=2, cols=3)
        for r, row in enumerate([["A", "A", "B"], ["C", "", "D"]]):
            for c, value in enumerate(row):
                table.cell(r, c).text = value
        self.blocks = list(iter_docx_blocks(doc))

    def test_locators_and_kinds(self):
        self.assertEqual(
            [b.locator for b in self.blocks],
            ["para:1", "para:2", "para:3", "table:1/r1", "table:1/r2"])
        self.assertEqual([b.kind for b in self.blocks],
                         ["paragraph", "paragraph", "paragraph",
                          "table_row", "table_row"])

    def test_paragraph_style_is_exposed(self):
        self.assertEqual(self.blocks[0].style, "Heading 1")
        self.assertEqual(self.blocks[1].text, "")
        self.assertEqual(self.blocks[2].style, "Normal")

    def test_table_cells_are_collapsed_and_joined(self):
        first, second = self.blocks[3], self.blocks[4]
        self.assertEqual(first.cells, ("A", "B"))
        self.assertEqual(first.text, "A | B")
        self.assertEqual(first.row_index, 1)
        self.assertEqual(second.cells, ("C", "D"))
        self.assertEqual(second.text, "C | D")
        self.assertEqual(second.row_index, 2)

    def test_numbered_flag(self):
        doc = docx.Document()
        plain = doc.add_paragraph("普通段落")
        numbered = doc.add_paragraph("自动编号段落")
        add_auto_numbering(numbered)
        blocks = list(iter_docx_blocks(doc))
        self.assertFalse(blocks[0].numbered)
        self.assertTrue(blocks[1].numbered)


if __name__ == "__main__":
    unittest.main()
