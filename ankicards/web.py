"""静态 HTML 的可见文本提取：标题、段落、列表项、表格行 -> block:N。

只做静态 DOM 解析，不执行 JS、不下载图片/样式/脚本，也不处理登录态。
`iter_html_blocks` 是 ingest 与 web-points 适配器的唯一遍历实现，避免两套索引漂移。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterator

from lxml import etree
from lxml import html as lxml_html

from .errors import CardError

DEFAULT_MAX_WEB_BLOCKS = 5000
_WS = re.compile(r"\s+")
_DROP_TAGS = ("script", "style", "noscript", "nav", "footer", "aside")
_BLOCK_TAGS = ("h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "tr")
_NESTED_TAGS = {"p", "li", "tr"}


class WebError(CardError):
    """HTML 解析失败；由 ingest 转成 IngestError（exit 2）。"""


@dataclass
class HtmlBlock:
    kind: str       # heading / paragraph / list_item / table_row
    locator: str    # block:N
    text: str


def _normalize(text: str) -> str:
    return _WS.sub(" ", text or "").strip()


def _element_text(element) -> str:
    return _normalize(" ".join(element.itertext()))


def _table_row_text(element) -> str:
    cells: list[str] = []
    for cell in element.xpath("./th|./td"):
        value = _element_text(cell)
        if not value:
            continue
        if cells and cells[-1] == value:
            continue
        cells.append(value)
    return " | ".join(cells)


def _has_block_ancestor(element, root) -> bool:
    parent = element.getparent()
    while parent is not None and parent is not root:
        if isinstance(parent.tag, str) and parent.tag.lower() in _NESTED_TAGS:
            return True
        parent = parent.getparent()
    return False


def iter_html_blocks(html: bytes | str, max_blocks: int = DEFAULT_MAX_WEB_BLOCKS
                     ) -> Iterator[HtmlBlock]:
    """按 DOM 顺序产出有效文本块；空块不计入 block:N。"""
    try:
        root = lxml_html.fromstring(html)
    except (etree.ParserError, ValueError, TypeError) as exc:
        raise WebError(f"无法解析 HTML: {exc}") from exc
    body = root.find("body")
    scope = body if body is not None else root
    for tag in _DROP_TAGS:
        for node in scope.xpath(f".//{tag}"):
            node.drop_tree()

    count = 0
    for element in scope.iter():
        tag = element.tag.lower() if isinstance(element.tag, str) else ""
        if tag not in _BLOCK_TAGS:
            continue
        if _has_block_ancestor(element, scope):
            continue
        if tag == "tr":
            text = _table_row_text(element)
        else:
            text = _element_text(element)
        if not text:
            continue
        count += 1
        if count > max_blocks:
            raise WebError(
                f"HTML 有效块超过 {max_blocks} 个；请拆分页面，或用 --max-blocks 放宽")
        kind = ("heading" if tag.startswith("h") else
                "paragraph" if tag == "p" else
                "list_item" if tag == "li" else "table_row")
        yield HtmlBlock(kind=kind, locator=f"block:{count}", text=text)
