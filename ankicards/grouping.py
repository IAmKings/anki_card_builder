"""把线性单元归并成可整段取用的组（groups）。

为什么需要它：`1. **环境准备**：安装 JDK 17` 后面紧跟的子项、续行，在版面
上属于同一个知识点；按行切卡会把子项丢掉、把答案在分号处截断。分组只做
「哪些单元属于同一段」这件事，不做语义判断，也不生成卡片。

单元来源与 ingest 完全一致（txt 物理行 / docx 块 / web 块），所以分组结果
可以和 ingest 的 locators 对上：组内单元首尾定位拼成区间定位（line:3-7）。

规则（确定性，可回归）：
- 空行/空块结束当前组，本身不入组；
- 标题、表格行各自成组（单成员组）；
- 编号点开新的 point 组；
- 无编号行在「缩进 / 列表前缀 / 上一行没说完」时并入当前 point 或 prose 组，
  否则另起 prose 组。
"""

from __future__ import annotations

import re
from typing import Callable, Iterable

#: 行尾是这些标点时，说明下一行大概率还是同一句/同一段的续行。
CONTINUE_TAIL = "，、：；,;:"

#: 子项前缀：- * + • ·、1)、（一）。
LIST_PREFIX = re.compile(r"^(?:[-*+•·]\s+|\d+[)）]\s+|[（(][一二三四五六七八九十\d]+[）)])")

TXT_HEADING_HASH = re.compile(r"^#{1,6}\s+(.+)$")
TXT_HEADING_CN = re.compile(r"^[一二三四五六七八九十百]+[、.．]\s*(.+)$")
TXT_ITEM_BOLD = re.compile(r"^\d+[.、]\s*\*\*(.+?)\*\*\s*[：:]\s*(.+)$")
TXT_ITEM_PLAIN = re.compile(r"^\d+[.、]\s*(.+?)\s*[：:]\s*(.+)$")

GROUP_KINDS = ("point", "prose", "heading", "table", "paragraph")


def txt_heading(text: str) -> str | None:
    """识别 Markdown `# 标题` 与中文 `一、标题`；返回去掉标记的标题。"""
    for pattern in (TXT_HEADING_HASH, TXT_HEADING_CN):
        match = pattern.match(text)
        if match:
            return match.group(1).strip()
    return None


def txt_point(text: str):
    """识别 `1. **关键词**：解释` / `1. 关键词：解释`，返回 (关键词, 解释)。"""
    for pattern in (TXT_ITEM_BOLD, TXT_ITEM_PLAIN):
        match = pattern.match(text)
        if match:
            return match.group(1).strip(), match.group(2).strip()
    return None


def classify_txt_line(unit: dict) -> str:
    """txt 单行分类：blank / heading / point / text。"""
    stripped = str(unit.get("text", "")).strip()
    if not stripped:
        return "blank"
    if txt_heading(stripped) is not None:
        return "heading"
    if txt_point(stripped) is not None:
        return "point"
    return "text"


def classify_docx_block(unit: dict) -> str:
    """docx 块分类；表头判定留给适配器，这里只管分组边界。"""
    if not str(unit.get("text", "")).strip():
        return "blank"
    if unit.get("kind") == "table_row":
        return "table"
    text = str(unit.get("text", "")).strip()
    style = str(unit.get("style", ""))
    if style.lower().startswith(("heading", "title")) or txt_heading(text) is not None:
        return "heading"
    if txt_point(text) is not None:
        return "point"
    return "text"


def classify_epub_block(unit: dict) -> str:
    """EPUB 的每个内容块本身就是语义边界：段落各自成组，不跨段合并。"""
    text = str(unit.get("text", "")).strip()
    if not text:
        return "blank"
    if unit.get("kind") == "heading":
        return "heading"
    if unit.get("kind") == "table_row":
        return "table"
    return "paragraph"


def classify_web_block(unit: dict) -> str:
    """web 块分类；列表项是「并入上一段」的显式信号。"""
    text = str(unit.get("text", "")).strip()
    if not text:
        return "blank"
    kind = unit.get("kind")
    if kind == "table_row":
        return "table"
    if kind == "heading":
        return "heading"
    if txt_point(text) is not None:
        return "point"
    if kind == "list_item":
        return "list_item"
    return "text"


def _joins(raw_text: str, prev_text: str, current_kind: str, kind: str) -> bool:
    if current_kind not in ("point", "prose"):
        return False
    if kind == "list_item":
        return True
    if raw_text[:1].isspace():
        return True
    if LIST_PREFIX.match(raw_text.strip()):
        return True
    return bool(prev_text) and prev_text.rstrip()[-1:] in CONTINUE_TAIL


def group_units(units: Iterable[dict],
                classify: Callable[[dict], str]) -> list[dict]:
    """把按序单元切成组；返回 [{id,kind,unit_locators,span,locator,chars}]。

    `units` 是 ingest 的单元 dict（至少含 locator 与 text）；返回顺序稳定。
    """
    groups: list[dict] = []
    current: dict | None = None

    def close() -> None:
        nonlocal current
        if current is not None and current["unit_locators"]:
            first = current["unit_locators"][0]
            last = current["unit_locators"][-1]
            head, _, start = first.partition(":")
            end = last.partition(":")[2]
            locator = first if first == last else f"{head}:{start}-{end}"
            groups.append({
                "id": f"g{len(groups) + 1}",
                "kind": current["kind"],
                "unit_locators": current["unit_locators"],
                "span": [first, last],
                "locator": locator,
                "chars": current["chars"],
            })
        current = None

    for unit in units:
        locator = str(unit.get("locator") or unit.get("id") or "")
        raw = str(unit.get("text", ""))
        kind = classify(unit)
        if kind == "blank":
            close()
            continue
        if kind in ("heading", "table", "paragraph"):
            close()
            current = {"kind": kind, "unit_locators": [locator],
                       "chars": len(raw.strip()), "last_text": raw}
            close()
            continue
        if kind == "point":
            close()
            current = {"kind": "point", "unit_locators": [locator],
                       "chars": len(raw.strip()), "last_text": raw}
            continue
        prev = current["last_text"] if current else ""
        current_kind = current["kind"] if current else ""
        if current is not None and _joins(raw, prev, current_kind, kind):
            current["unit_locators"].append(locator)
            current["chars"] += len(raw.strip())
            current["last_text"] = raw
            continue
        close()
        current = {"kind": "prose", "unit_locators": [locator],
                   "chars": len(raw.strip()), "last_text": raw}

    close()
    return groups


def missing_units(units: Iterable[dict], groups: Iterable[dict]) -> list[str]:
    """返回既非空行、又没被任何组覆盖的定位；用于 ingest 自检。"""
    non_blank = [str(u.get("locator") or u.get("id"))
                 for u in units if str(u.get("text", "")).strip()]
    covered: set[str] = set()
    for group in groups:
        covered.update(group["unit_locators"])
    return [locator for locator in non_blank if locator not in covered]
