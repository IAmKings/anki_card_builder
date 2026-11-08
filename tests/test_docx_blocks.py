"""DOCX 共享遍历：ingest 与 adapter 使用同一套段落/表格定位计数。"""

import unittest

try:
    import docx  # type: ignore
    HAS_DOCX = True
except ImportError:  # pragma: no cover
    HAS_DOCX = False

from ankicards.docx import iter_docx_blocks


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


if __name__ == "__main__":
    unittest.main()
