"""DOCX body 遍历：ingest 与 docx-points 共用的唯一定位计数。

定位语法：
- para:N         body 内第 N 个 w:p（1 基；空段落也计数；表格内段落不计）
- table:T/rR     第 T 个 w:tbl 的第 R 行（1 基）
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterator


@dataclass(frozen=True)
class DocxBlock:
    """一个可寻址的 DOCX 文本块。"""

    kind: str                       # "paragraph" / "table_row"
    locator: str                    # para:N / table:T/rR
    text: str
    style: str = ""                 # 段落样式名；表格行为空
    cells: tuple[str, ...] = ()     # 表格行：去空、折叠相邻重复后的单元格
    row_index: int = 0              # 表格行号（1 基）；段落为 0
    numbered: bool = False          # 段落是否带 Word 自动编号（w:numPr）


def iter_docx_blocks(doc: Any) -> Iterator[DocxBlock]:
    """按 body 顺序产出 DocxBlock；python-docx 延迟导入，供 CLI 无依赖运行。"""
    from docx.oxml.ns import qn
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    paragraph_index = 0
    table_index = 0
    for child in doc.element.body.iterchildren():
        if child.tag == qn("w:p"):
            paragraph_index += 1
            paragraph = Paragraph(child, doc)
            style = (paragraph.style.name if paragraph.style is not None else "") or ""
            pPr = child.find(qn("w:pPr"))
            numbered = pPr is not None and pPr.find(qn("w:numPr")) is not None
            yield DocxBlock(
                kind="paragraph",
                locator=f"para:{paragraph_index}",
                text=paragraph.text,
                style=style,
                numbered=numbered,
            )
        elif child.tag == qn("w:tbl"):
            table_index += 1
            table = Table(child, doc)
            for row_index, row in enumerate(table.rows, 1):
                cells: list[str] = []
                for cell in row.cells:
                    value = cell.text.strip()
                    if value and (not cells or cells[-1] != value):
                        cells.append(value)
                yield DocxBlock(
                    kind="table_row",
                    locator=f"table:{table_index}/r{row_index}",
                    text=" | ".join(cells),
                    cells=tuple(cells),
                    row_index=row_index,
                )
