"""可卡性预检：在写 plan 之前，先用客观指标决定卡型与密度口径。

为什么要单独一个模块：同一份 PDF，按「页」算和按「行」算会得到相反的结论——
页级编号点 0%、平均 1,017 字，行级编号点 24%、平均 31 字。选路必须用**行级**结构
指标（一行是不是一个可独立出卡的单元），页级指标只用来提示「长引用会不会跨页」。

本模块只读 ingest 清单，不写文件、不调用模型；判定是启发式，冲突时以人工判断为准。
"""

from __future__ import annotations

import re
import statistics
from typing import Any

#: 编号点：`1.` `1.2` `（一）` `一、` `第X条`。
_NUMBERING_RE = re.compile(
    r"^\s*(?:\d+(?:\.\d+)*[.、)．]|[（(][一二三四五六七八九十\d]+[)）]"
    r"|[一二三四五六七八九十]+[、.．]|第[一二三四五六七八九十百千\d]+[条款项章节])")
_SENTENCE_SPLIT_RE = re.compile(r"[。！？!?…]+")
_TABLE_PREFIXES = ("table:",)

#: 阈值与 policy §12 保持一致，改这里要同步改文档。
NUMBERING_ADAPTER_MIN = 0.30   # 高于此值才考虑 *-points
NUMBERING_ADAPTER_MAX = 0.10   # 低于此值禁止 *-points
DIGIT_FACT_MIN = 0.03          # 低于此值不出 fact
DIGIT_FACT_MAIN = 0.30         # 高于此值 fact 可为主力
LONG_UNIT_RATIO_MAX = 0.20     # >300 字的单元占比，超过就是长引用风险
QUOTE_DENSITY_MIN = 0.80       # 引号/段，高于此值偏对话或引语
TABLE_SHARE_MIN = 0.20         # 表格行占比，高于此值词表型资料


def _locator(unit: dict) -> str:
    return str(unit.get("locator") or unit.get("id") or "")


def structural_units(manifest: dict) -> list[str]:
    """把清单拆成「一行/一段一个可出卡单元」，用于结构指标。

    PDF 的 unit 是页，必须再按行拆——否则一页上千字会把所有比例稀释掉。
    DOCX 的段落、EPUB 的 `<p>`、TXT 的行本来就是最小单元，不再拆。
    """
    fmt = str(manifest.get("format") or "")
    texts: list[str] = []
    for unit in manifest.get("units") or []:
        if not isinstance(unit, dict):
            continue
        raw = str(unit.get("text") or "")
        if fmt == "pdf":
            texts.extend(line.strip() for line in raw.splitlines() if line.strip())
        else:
            stripped = raw.strip()
            if stripped:
                texts.append(stripped)
    return texts


def page_texts(manifest: dict) -> list[str]:
    """页级文本（只有 PDF 有意义）；其它格式返回空列表。"""
    if str(manifest.get("format") or "") != "pdf":
        return []
    return [str(u.get("text") or "").strip() for u in manifest.get("units") or []
            if isinstance(u, dict) and str(u.get("text") or "").strip()]


def _ratio(part: int, whole: int) -> float:
    return part / whole if whole else 0.0


def analyze(manifest: dict) -> dict[str, Any]:
    """算五项结构指标 + 页级版面指标，并给出选路建议。"""
    units = structural_units(manifest)
    pages = page_texts(manifest)
    sentences = [s.strip() for s in _SENTENCE_SPLIT_RE.split("\n".join(units)) if s.strip()]
    lens = [len(t) for t in units]
    all_units = [u for u in manifest.get("units") or [] if isinstance(u, dict)]

    structural = {
        "units": len(units),
        "numbering_ratio": _ratio(sum(1 for t in units if _NUMBERING_RE.match(t)), len(units)),
        "digit_sentence_ratio": _ratio(sum(1 for s in sentences if re.search(r"\d", s)),
                                       len(sentences)),
        "avg_chars": statistics.mean(lens) if lens else 0.0,
        "median_chars": statistics.median(lens) if lens else 0.0,
        "long_unit_ratio": _ratio(sum(1 for n in lens if n > 300), len(lens)),
        "quote_density": _ratio(
            sum(t.count("「") + t.count("“") for t in units), len(units)),
        "table_row_ratio": _ratio(
            sum(1 for u in all_units if _locator(u).startswith(_TABLE_PREFIXES)), len(all_units)),
    }

    page_chars = [len(t.replace("\n", "")) for t in pages]
    layout = {
        "pages": len(pages),
        "avg_chars_per_page": statistics.mean(page_chars) if page_chars else 0.0,
        "long_page_ratio": _ratio(sum(1 for n in page_chars if n > 300), len(page_chars)),
    }

    return {
        "format": manifest.get("format"),
        "structural": structural,
        "layout": layout,
        "advice": _advice(structural, layout),
    }


def _advice(structural: dict, layout: dict) -> list[str]:
    """把指标翻译成决策，避免读者自己对照阈值。"""
    tips: list[str] = []
    numbering = structural["numbering_ratio"]
    if numbering >= NUMBERING_ADAPTER_MIN:
        tips.append(f"编号点 {numbering:.0%}：可尝试 *-points 适配器；"
                    "PDF 先按行核对「一问一答」是否成立，折行会切断答案")
    elif numbering < NUMBERING_ADAPTER_MAX:
        tips.append(f"编号点 {numbering:.0%}：禁止 *-points，走 ingest → plan")

    digits = structural["digit_sentence_ratio"]
    if digits < DIGIT_FACT_MIN:
        tips.append(f"数字句 {digits:.0%}：不出 fact，改用 claim/style/phrase")
    elif digits > DIGIT_FACT_MAIN:
        tips.append(f"数字句 {digits:.0%}：fact 可为主力")

    if structural["long_unit_ratio"] > LONG_UNIT_RATIO_MAX:
        tips.append(f"长单元 {structural['long_unit_ratio']:.0%}（>300 字）："
                    "长引用风险，优先 EPUB；PDF 用 page:N-M")

    if structural["quote_density"] > QUOTE_DENSITY_MIN:
        tips.append(f"引号密度 {structural['quote_density']:.1f}/段：对话或引语型，"
                    "phrase 与情节卡更合适")

    if structural["table_row_ratio"] > TABLE_SHARE_MIN:
        tips.append(f"表格行 {structural['table_row_ratio']:.0%}：词表型资料，"
                    "fact 密度可以拉高")

    if layout["pages"] and layout["long_page_ratio"] > LONG_UNIT_RATIO_MAX:
        tips.append(f"页均 {layout['avg_chars_per_page']:.0f} 字、"
                    f"{layout['long_page_ratio']:.0%} 的页超过 300 字："
                    "版面密度高，PDF 定位注意跨页")
    return tips


def format_report(result: dict) -> str:
    """人类可读输出：先结构指标（决定选路），再版面指标（只看跨页风险）。"""
    s = result["structural"]
    layout = result["layout"]
    lines = [
        f"格式：{result['format']}　　结构单元：{s['units']}（PDF 已按行拆）",
        f"编号点 {s['numbering_ratio']:.1%}　数字句 {s['digit_sentence_ratio']:.1%}　"
        f"平均段长 {s['avg_chars']:.0f} 字（中位 {s['median_chars']:.0f}）　"
        f">300 字 {s['long_unit_ratio']:.1%}",
        f"引号密度 {s['quote_density']:.2f}/段　表格行 {s['table_row_ratio']:.1%}",
    ]
    if layout["pages"]:
        lines.append(f"版面：{layout['pages']} 页，页均 {layout['avg_chars_per_page']:.0f} 字，"
                     f">300 字的页 {layout['long_page_ratio']:.1%}")
    if result["advice"]:
        lines.append("建议：")
        lines.extend(f"- {tip}" for tip in result["advice"])
    return "\n".join(lines)
