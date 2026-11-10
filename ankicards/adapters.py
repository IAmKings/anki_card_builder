"""源格式适配器：把 MD/TXT 等原始资料解析成 DeckSpec 形状，交给同一个构建入口。

约定：适配器只产出「牌组名 + 子牌组 + 卡片」的纯数据，不碰 genanki、不建模型。
新增一种格式 = 在这个文件里加一个带 @register 的函数，不需要再复制打包逻辑。
"""

from __future__ import annotations

import json
import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from .docx import iter_docx_blocks
from .errors import CardError
from .quality import TABLE_FIRST_CELLS, TABLE_HEADERS, check_card
from .schema import WEB_LOCATOR_RE
from .web import HtmlBlock, WebError, iter_html_blocks

ADAPTERS: dict[str, object] = {}


def register(name: str):
    def decorate(func):
        ADAPTERS[name] = func
        return func

    return decorate


#: 未出卡的合法理由；报告里按这个枚举统计，不要随手发明新值。
SKIP_REASONS = ("blank", "heading", "not_point", "continuation",
                "table_header", "duplicate_input")


@dataclass
class DeckData:
    name: str
    sections: dict[str, list[dict]] = field(default_factory=dict)
    source_kind: str = "unknown"
    warnings: list[str] = field(default_factory=list)
    #: 每个没变成卡片的源单元都要在这里留一条，用来解释覆盖率。
    skipped: list[dict] = field(default_factory=list)
    #: quality.check_card 的结论，附上定位；默认只报告，--strict 才拦。
    findings: list[dict] = field(default_factory=list)

    def add(self, section: str, card: dict) -> None:
        self.sections.setdefault(section or "默认", []).append(card)

    def add_checked(self, section: str, card: dict, unit_text: str | None = None) -> None:
        """加卡并跑内容层规则；定位取自卡片的 source。"""
        self.add(section, card)
        for finding in check_card(card, unit_text=unit_text):
            self.findings.append({
                "locator": card.get("source", ""),
                "rule": finding.rule,
                "level": finding.level,
                "message": finding.message,
            })

    def skip(self, locator: str, reason: str, note: str = "") -> None:
        if reason not in SKIP_REASONS:  # pragma: no cover - 防御
            raise ValueError(f"未知的未出卡理由: {reason}")
        self.skipped.append({"locator": locator, "reason": reason, "note": note})

    def count_skipped(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for item in self.skipped:
            counts[item["reason"]] = counts.get(item["reason"], 0) + 1
        return counts

    def count_findings(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for item in self.findings:
            counts[item["rule"]] = counts.get(item["rule"], 0) + 1
        return counts

    @property
    def card_count(self) -> int:
        return sum(len(cards) for cards in self.sections.values())


def _provenance(card) -> str:
    parts = [getattr(card, "source_file", "") or ""]
    section = getattr(card, "source_section", "") or ""
    if section:
        parts.append(section)
    return " > ".join(p for p in parts if p)


def _to_card(card) -> dict:
    """把 src.models.Flashcard 转成 ankicards 的卡片 dict。"""
    if getattr(card, "card_type", "basic") == "cloze":
        result = {"type": "cloze", "text": card.front, "extra": card.back}
    else:
        result = {"type": "qa", "q": card.front, "a": card.back}
    result["source"] = _provenance(card)
    tags = [t for t in getattr(card, "tags", []) if t]
    if tags:
        result["tags"] = tags
    return result


@register("android-md")
def from_android_md(source: Path, name: str = "Android面试") -> DeckData:
    """Android 面试题库：复用 src/parsers + 质量过滤 + 去重。"""
    from src.parsers.kotlin_md import KotlinMDParser
    from src.processing.deduplicator import Deduplicator
    from src.processing.quality_filter import QualityFilter

    files = sorted(p for p in source.glob("*.md") if not p.name.startswith("."))
    if not files:
        raise CardError(f"{source} 下没有 .md 文件")

    cards = []
    for path in files:
        cards.extend(KotlinMDParser(path).parse())
    cards = QualityFilter.validate(cards)
    cards = Deduplicator(threshold=0.85).deduplicate(cards)

    deck = DeckData(name=name, source_kind="md")
    for card in cards:
        full = getattr(card, "deck_name", name) or name
        section = full.split("::", 1)[1] if "::" in full else full
        deck.add(section, _to_card(card))
    return deck


# ---------------------------------------------------------------------------
# MQTT：原 generate_mqtt.py 的解析与题目构造，搬成纯数据适配器
# ---------------------------------------------------------------------------

_ITEM = re.compile(r"^(\d+)\.\s+\*\*(.+?)\*\*[：:]\s*(.+)")
_SECTION = re.compile(r"^##\s+[一二三四五六七八九十]+[、.]\s*(.+?)(?:（\d|$)")
_DEFINITION_MARKERS = ("全称", "含义", "概念", "定义")
_MAX_OPTION_LEN = 150
_MAX_HINT_LEN = 150


@dataclass
class _Point:
    number: int
    keyword: str
    explanation: str
    section: str


def _parse_points(path: Path) -> list[_Point]:
    points: list[_Point] = []
    section = ""
    for line in path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text:
            continue
        match = _SECTION.match(text)
        if match:
            section = match.group(1).removeprefix("MQTT ").strip()
            continue
        match = _ITEM.match(text)
        if match:
            points.append(_Point(int(match.group(1)), match.group(2).strip(),
                                 match.group(3).strip(), section))
    return points


def _front(keyword: str) -> str:
    if any(marker in keyword for marker in _DEFINITION_MARKERS) or len(keyword) <= 5:
        return f"什么是{keyword}？"
    return keyword


def _truncate(text: str, limit: int) -> str:
    text = text.strip()
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _tags(section: str, kind: str) -> list[str]:
    return ["source:mqtt", "topic:mqtt", f"MQTT::{section}", f"type:{kind}"]


def _mc_card(point: _Point, points: list[_Point], index: int) -> dict:
    correct = _truncate(point.explanation, _MAX_OPTION_LEN)
    distractors: list[str] = []
    seen = {correct}
    ordered = ([p for p in points if p.section == point.section]
               + [p for p in points if p.section != point.section])
    for other in ordered:
        candidate = _truncate(other.explanation, _MAX_OPTION_LEN)
        if candidate in seen:
            continue
        seen.add(candidate)
        distractors.append(candidate)
        if len(distractors) >= 3:
            break
    while len(distractors) < 3:
        distractors.append("以上选项都不正确")

    position = point.number % 4
    options, slot = [], 0
    for pos in range(4):
        if pos == position:
            options.append(correct)
        else:
            options.append(distractors[slot])
            slot += 1
    front = _front(point.keyword) + "<br><br>" + "<br>".join(
        f"{chr(ord('A') + i)}. {opt}" for i, opt in enumerate(options))
    hint = _truncate(f"本题考察「{point.keyword}」，请结合 MQTT 协议整体框架理解其核心定义与适用场景。",
                     _MAX_HINT_LEN)
    back = f"正确答案：{chr(ord('A') + position)}. {correct}<br><br>扩展：{hint}"
    return {"type": "qa", "q": front, "a": back, "source": f"{point.section} > {point.number}",
            "tags": _tags(point.section, "mc")}


@register("mqtt-md")
def from_mqtt_md(source: Path, name: str = "MQTT协议") -> DeckData:
    """MQTT 知识点 MD：每个点生成一张问答 + 一张四选一。"""
    files = [source] if source.is_file() else sorted(source.glob("*.md"))
    if not files:
        raise CardError(f"{source} 下没有 .md 文件")
    points: list[_Point] = []
    for path in files:
        points.extend(_parse_points(path))
    if not points:
        raise CardError(f"{source} 里没有解析出知识点（格式需形如 `1. **关键词**：解释`）")

    deck = DeckData(name=name, source_kind="md")
    for index, point in enumerate(points):
        deck.add(point.section, {
            "type": "qa",
            "q": _front(point.keyword),
            "a": point.explanation,
            "source": f"{point.section} > {point.number}",
            "tags": _tags(point.section, "qa"),
        })
        deck.add(point.section, _mc_card(point, points, index))
    return deck


# ---------------------------------------------------------------------------
# DOCX：标题分段 + “编号点/表格行”两类知识点
# ---------------------------------------------------------------------------

_DOCX_ITEM_BOLD = re.compile(r"^\d+[.、]\s*\*\*(.+?)\*\*\s*[：:]\s*(.+)$")
_DOCX_ITEM_PLAIN = re.compile(r"^\d+[.、]\s*(.+?)\s*[：:]\s*(.+)$")
# 词表真值在 quality.py；这里只是沿用旧名字，避免两处各写一份。
_DOCX_TABLE_HEADERS = TABLE_HEADERS
_DOCX_HEADER_FIRST = TABLE_FIRST_CELLS


def _docx_heading(text: str) -> str:
    """去掉标题前面的“一、”“1.”等编号，留作子牌组名。"""
    return re.sub(r"^[一二三四五六七八九十百0-9]+[、.．]\s*", "", text).strip() or text


def _docx_point(text: str):
    for pattern in (_DOCX_ITEM_BOLD, _DOCX_ITEM_PLAIN):
        match = pattern.match(text)
        if match:
            return match.group(1).strip(), match.group(2).strip()
    return None


# ---------------------------------------------------------------------------
# groups 路径：ingest 已经分好组，适配器按组取点并把续行/子项并回答案
# ---------------------------------------------------------------------------

def _manifest_units(manifest, expected: str) -> tuple[dict[str, str], list[dict]]:
    """校验 --ingest 产物，返回（定位→文本, groups）。"""
    if not isinstance(manifest, dict):
        raise CardError("--ingest 需要一个 ingest 产物（JSON 对象）")
    fmt = manifest.get("format")
    if fmt != expected:
        raise CardError(f"--ingest 的 format 是 {fmt!r}，当前适配器需要 {expected!r}")
    units = manifest.get("units")
    groups = manifest.get("groups")
    if not isinstance(units, list) or not units:
        raise CardError("--ingest 产物里没有 units")
    if not isinstance(groups, list) or not groups:
        raise CardError("--ingest 产物里没有 groups；请用当前版本重新跑 ingest")
    by_locator: dict[str, str] = {}
    for unit in units:
        if not isinstance(unit, dict):
            raise CardError("--ingest 产物: units 必须是对象数组")
        locator = unit.get("locator") or unit.get("id")
        if not isinstance(locator, str) or not locator:
            raise CardError("--ingest 产物: unit 缺少 locator")
        if locator in by_locator:
            raise CardError(f"--ingest 产物里定位重复: {locator}")
        by_locator[locator] = str(unit.get("text", ""))
    return by_locator, groups


def _grouped_heading(text: str, fmt: str) -> str:
    if fmt in ("txt", "web"):
        return _txt_heading(text) or _docx_heading(text)
    return _docx_heading(text)


def _from_groups(manifest, fmt: str, name: str,
                 section_prefix: str | None) -> DeckData:
    """按 ingest 的 groups 出卡；答案 = 编号点解释 + 组内其余文本（单空格拼接）。"""
    units, groups = _manifest_units(manifest, fmt)
    deck = DeckData(name=name, source_kind=fmt)
    section = ""
    card_count = 0
    for group in groups:
        if not isinstance(group, dict):
            raise CardError("--ingest 产物: groups 里必须是对象")
        span = group.get("locator")
        members = group.get("unit_locators")
        kind = group.get("kind")
        if not isinstance(span, str) or not span:
            raise CardError("--ingest 产物: group 缺少 locator")
        if not isinstance(members, list) or not members:
            raise CardError(f"--ingest 产物: group {span} 缺少 unit_locators")
        texts = []
        for member in members:
            if member not in units:
                raise CardError(f"--ingest 产物: group {span} 引用了不存在的单元 {member!r}")
            texts.append(units[member])

        if kind == "heading":
            section = _grouped_heading(texts[0].strip(), fmt)
            deck.skip(span, "heading", section)
            continue
        if kind == "table":
            if fmt != "docx":
                deck.skip(span, "not_point", "表格行不自动出题")
                continue
            cells = [cell.strip() for cell in texts[0].split(" | ") if cell.strip()]
            if len(cells) < 2:
                deck.skip(span, "not_point", "表格行少于两列")
                continue
            if cells[0] in _DOCX_HEADER_FIRST and cells[1] in _DOCX_TABLE_HEADERS:
                deck.skip(span, "table_header")
                continue
            deck.add_checked(section, {
                "type": "qa",
                "q": cells[0],
                "a": " | ".join(cells[1:]),
                "source": span,
                "tags": ["source:docx", "type:qa"],
            }, unit_text=texts[0])
            card_count += 1
            continue
        if kind != "point":
            deck.skip(span, "not_point")
            continue
        point = _txt_point(texts[0].strip())
        if point is None:
            deck.skip(span, "not_point", "组首不是编号点")
            continue
        keyword, explanation = point
        rest = " ".join(text.strip() for text in texts[1:] if text.strip())
        answer = explanation if not rest else f"{explanation} {rest}"
        tags = [f"source:{fmt}", "type:qa"]
        if section and section_prefix:
            tags.append(f"{section_prefix}::{section}")
        deck.add_checked(section, {
            "type": "qa",
            "q": _front(keyword),
            "a": answer,
            "source": span,
            "tags": tags,
        }, unit_text="\n".join(text.strip() for text in texts))
        card_count += 1

    if card_count == 0:
        raise CardError("没有解析出编号点；检查源文档或 --ingest 产物")
    return deck


@register("docx-points")
def from_docx_points(source: Path, name: str = "DOCX知识点",
                     ingest: dict | None = None) -> DeckData:
    """DOCX 知识点：标题 → 子牌组，编号段落/表格行 → 问答，source 用 para/table 定位。

    传 `ingest`（ingest 产物）时走 groups 路径：按组取点，把续行并回答案。
    """
    if ingest is not None:
        return _from_groups(ingest, "docx", name, section_prefix=None)
    source = Path(source)
    if source.is_dir():
        raise CardError("docx-points 只接受单个 .docx；请传文件路径")
    if source.suffix.lower() != ".docx":
        raise CardError(f"docx-points 只支持 .docx，实际为 {source.suffix or '(无扩展名)'}")

    try:
        import docx  # type: ignore
    except ImportError as exc:  # pragma: no cover - 依赖环境
        raise CardError("需要 python-docx：pip install -r requirements.txt") from exc
    from docx.opc.exceptions import PackageNotFoundError
    from lxml.etree import XMLSyntaxError
    try:
        document = docx.Document(str(source))
    except (PackageNotFoundError, zipfile.BadZipFile, XMLSyntaxError,
            KeyError, ValueError, OSError) as exc:
        raise CardError(f"无法打开 DOCX（损坏或已加密）: {exc}") from exc

    deck = DeckData(name=name, source_kind="docx")
    section = ""
    card_count = 0
    auto_numbered: list[str] = []
    last_was_point = False
    for block in iter_docx_blocks(document):
        if block.kind == "paragraph":
            text = block.text.strip()
            if not text:
                deck.skip(block.locator, "blank")
                continue
            if block.style.lower().startswith("heading") or block.style.startswith("标题"):
                section = _docx_heading(text)
                deck.skip(block.locator, "heading", section)
                last_was_point = False
                continue
            point = _docx_point(text)
            if point is None:
                if block.numbered:
                    auto_numbered.append(block.locator)
                deck.skip(block.locator, "continuation" if last_was_point else "not_point")
                continue
            keyword, explanation = point
            deck.add_checked(section, {
                "type": "qa",
                "q": _front(keyword),
                "a": explanation,
                "source": block.locator,
                "tags": ["source:docx", "type:qa"],
            }, unit_text=text)
            last_was_point = True
            card_count += 1
        elif block.kind == "table_row":
            cells = block.cells
            if len(cells) < 2:
                deck.skip(block.locator, "not_point", "表格行少于两列")
                continue
            # 只有“首格也是表头词”时才丢首行；避免把 ["端口","解释"] 这类真实数据误判为表头。
            if (block.row_index == 1
                    and cells[0] in _DOCX_HEADER_FIRST
                    and cells[1] in _DOCX_TABLE_HEADERS):
                deck.skip(block.locator, "table_header")
                continue
            deck.add_checked(section, {
                "type": "qa",
                "q": cells[0],
                "a": " | ".join(cells[1:]),
                "source": block.locator,
                "tags": ["source:docx", "type:qa"],
            })
            last_was_point = False
            card_count += 1

    if auto_numbered:
        sample = "、".join(auto_numbered[:5])
        suffix = "…" if len(auto_numbered) > 5 else ""
        message = (
            f"检测到 {len(auto_numbered)} 个 Word 自动编号段落（{sample}{suffix}）："
            "python-docx 不会把自动编号写进段落文本，无法按 `1. **关键词**：解释` 解析；"
            "请改为手写编号，或把编号粘贴为文本。")
        if card_count == 0:
            raise CardError(message)
        deck.warnings.append(message)

    if card_count == 0:
        raise CardError(
            "没有解析出编号点或表格行；段落需形如 `1. **关键词**：解释`，"
            "或使用至少两列的表格")
    return deck


# ---------------------------------------------------------------------------
# TXT：标题分段 + “编号点”，source 用物理行号 line:N
# ---------------------------------------------------------------------------

_TXT_HEADING_HASH = re.compile(r"^#{1,6}\s+(.+)$")
_TXT_HEADING_CN = re.compile(r"^[一二三四五六七八九十百]+[、.．]\s*(.+)$")
_TXT_ITEM_BOLD = re.compile(r"^\d+[.、]\s*\*\*(.+?)\*\*\s*[：:]\s*(.+)$")
_TXT_ITEM_PLAIN = re.compile(r"^\d+[.、]\s*(.+?)\s*[：:]\s*(.+)$")


def _txt_heading(text: str) -> str | None:
    for pattern in (_TXT_HEADING_HASH, _TXT_HEADING_CN):
        match = pattern.match(text)
        if match:
            return match.group(1).strip()
    return None


def _txt_point(text: str):
    for pattern in (_TXT_ITEM_BOLD, _TXT_ITEM_PLAIN):
        match = pattern.match(text)
        if match:
            return match.group(1).strip(), match.group(2).strip()
    return None


@register("txt-points")
def from_txt_points(source: Path, name: str = "TXT知识点",
                    ingest: dict | None = None) -> DeckData:
    """TXT 知识点：标题行 → 子牌组，编号行 → 问答，source=line:N。

    传 `ingest`（ingest 产物）时走 groups 路径：按组取点，把续行并回答案，
    source 写区间（如 line:3-5）。
    """
    if ingest is not None:
        return _from_groups(ingest, "txt", name, section_prefix="TXT")
    source = Path(source)
    if source.is_dir():
        raise CardError("txt-points 只接受单个 .txt；请传文件路径")
    if source.suffix.lower() != ".txt":
        raise CardError(f"txt-points 只支持 .txt，实际为 {source.suffix or '(无扩展名)'}")
    try:
        text = source.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError as exc:
        raise CardError("TXT 必须是 UTF-8；请用 UTF-8 重新保存后重试") from exc
    except OSError as exc:
        raise CardError(f"无法读取 TXT: {exc}") from exc

    deck = DeckData(name=name, source_kind="txt")
    section = ""
    card_count = 0
    last_was_point = False
    for number, line in enumerate(text.splitlines(), 1):
        locator = f"line:{number}"
        stripped = line.strip()
        if not stripped:
            deck.skip(locator, "blank")
            continue
        heading = _txt_heading(stripped)
        if heading is not None:
            section = heading
            deck.skip(locator, "heading", heading)
            last_was_point = False
            continue
        point = _txt_point(stripped)
        if point is None:
            deck.skip(locator, "continuation" if last_was_point else "not_point")
            continue
        keyword, explanation = point
        tags = ["source:txt", "type:qa"]
        if section:
            tags.append(f"TXT::{section}")
        deck.add_checked(section, {
            "type": "qa",
            "q": _front(keyword),
            "a": explanation,
            "source": locator,
            "tags": tags,
        }, unit_text=stripped)
        last_was_point = True
        card_count += 1

    if card_count == 0:
        raise CardError(
            "没有解析出编号点；TXT 需形如 `1. **关键词**：解释` 或 `1. 关键词：解释`，"
            "标题可用 `# 标题` 或 `一、标题`")
    return deck


# ---------------------------------------------------------------------------
# Web：标题 + 编号段落/列表项，source 用提取块号 block:N
# ---------------------------------------------------------------------------


def _read_web_blocks(source: Path) -> list[HtmlBlock]:
    suffix = source.suffix.lower()
    if suffix == ".json":
        try:
            data = json.loads(source.read_text(encoding="utf-8-sig"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise CardError(f"无法读取 web ingest 产物: {exc}") from exc
        if not isinstance(data, dict) or data.get("format") != "web":
            raise CardError("JSON 不是 web 的 ingest 产物（format 需为 web）")
        units = data.get("units")
        if not isinstance(units, list) or not units:
            raise CardError("web ingest 产物里没有 units")
        blocks: list[HtmlBlock] = []
        seen: set[str] = set()
        for unit in units:
            if not isinstance(unit, dict):
                raise CardError("web ingest 产物: units 必须是对象数组")
            locator = unit.get("locator") or unit.get("id")
            if not isinstance(locator, str) or not WEB_LOCATOR_RE.fullmatch(locator):
                raise CardError(f"web ingest 产物: 非法 block 定位 {locator!r}")
            if locator in seen:
                raise CardError(f"web ingest 产物: block 定位重复 {locator}")
            seen.add(locator)
            kind = unit.get("kind") or "paragraph"
            if kind not in ("heading", "paragraph", "list_item", "table_row"):
                kind = "paragraph"
            blocks.append(HtmlBlock(kind=kind, locator=locator,
                                    text=str(unit.get("text", ""))))
        return blocks
    if suffix in (".html", ".htm"):
        try:
            return list(iter_html_blocks(source.read_bytes()))
        except OSError as exc:
            raise CardError(f"无法读取 HTML: {exc}") from exc
        except WebError as exc:
            raise CardError(str(exc)) from exc
    raise CardError(
        f"web-points 只支持 .html/.htm 或 web ingest .json，实际为 {suffix or '(无扩展名)'}")


@register("web-points")
def from_web_points(source: Path, name: str = "Web知识点",
                    ingest: dict | None = None) -> DeckData:
    """网页知识点：标题块 → 子牌组，编号段落/列表项 → 问答，source=block:N。

    传 `ingest`（ingest 产物）时走 groups 路径：按组取点，把列表子项并回答案。
    """
    if ingest is not None:
        return _from_groups(ingest, "web", name, section_prefix="WEB")
    source = Path(source)
    if source.is_dir():
        raise CardError("web-points 只接受单个 .html/.htm 或 web ingest .json；请传文件路径")
    blocks = _read_web_blocks(source)
    deck = DeckData(name=name, source_kind="web")
    section = ""
    card_count = 0
    last_was_point = False
    for block in blocks:
        text = block.text.strip()
        if not text:
            deck.skip(block.locator, "blank")
            continue
        if block.kind == "heading":
            section = _txt_heading(text) or _docx_heading(text) or text
            deck.skip(block.locator, "heading", section)
            last_was_point = False
            continue
        if block.kind == "table_row":
            deck.skip(block.locator, "not_point", "表格行不自动出题")
            last_was_point = False
            continue
        point = _txt_point(text) or _docx_point(text)
        if point is None:
            deck.skip(block.locator, "continuation" if last_was_point else "not_point")
            continue
        keyword, explanation = point
        tags = ["source:web", "type:qa"]
        if section:
            tags.append(f"WEB::{section}")
        deck.add_checked(section, {
            "type": "qa",
            "q": _front(keyword),
            "a": explanation,
            "source": block.locator,
            "tags": tags,
        }, unit_text=text)
        last_was_point = True
        card_count += 1
    if card_count == 0:
        raise CardError(
            "没有解析出编号点；网页需有标题（h1-h6）和形如 "
            "`1. **关键词**：解释` 的段落/列表项；表格行不自动出题")
    return deck


# ---------------------------------------------------------------------------


def build_report(deck: DeckData) -> dict:
    """import-report.json 的内容：卡片数、未出卡理由、内容规则命中。

    这是「覆盖率账本」的第一版：每个没变成卡片的源单元，都应该能在
    skipped 里找到理由；找不到就是没被看过，而不是「不需要」。
    """
    skipped_by_reason = deck.count_skipped()
    findings_by_rule = deck.count_findings()
    findings_by_level: dict[str, int] = {}
    for item in deck.findings:
        findings_by_level[item["level"]] = findings_by_level.get(item["level"], 0) + 1
    return {
        "deck": deck.name,
        "source_kind": deck.source_kind,
        "sections": len([cards for cards in deck.sections.values() if cards]),
        "cards": deck.card_count,
        "skipped_total": len(deck.skipped),
        "skipped_by_reason": dict(sorted(skipped_by_reason.items())),
        "findings_total": len(deck.findings),
        "findings_by_rule": dict(sorted(findings_by_rule.items())),
        "findings_by_level": dict(sorted(findings_by_level.items())),
        "skipped": deck.skipped,
        "findings": deck.findings,
    }


def write_deck(deck: DeckData, out_dir: str | Path, force: bool = False) -> Path:
    """把适配结果写成 <out>/deck.json + <out>/cards/NN.json + <out>/import-report.json。

    目标目录已有卡片时默认拒绝，避免一次误操作删掉手工卡片；确需覆盖请传 force=True。
    """
    out = Path(out_dir)
    cards_dir = out / "cards"
    existing = sorted(cards_dir.glob("*.json")) if cards_dir.is_dir() else []
    if existing and not force:
        raise CardError(
            f"{cards_dir} 已有 {len(existing)} 个卡片文件，拒绝覆盖；确认要重建请加 --force")
    cards_dir.mkdir(parents=True, exist_ok=True)
    for stale in cards_dir.glob("*.json"):
        stale.unlink()

    (out / "deck.json").write_text(
        json.dumps({"name": deck.name, "source_kind": deck.source_kind},
                   ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    index = 0
    for section, cards in deck.sections.items():
        if not cards:
            continue
        index += 1
        path = cards_dir / f"{index:02d}.json"
        path.write_text(
            json.dumps({"deck": section, "cards": cards}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8")
    (out / "import-report.json").write_text(
        json.dumps(build_report(deck), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return out
