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

ADAPTERS: dict[str, object] = {}


def register(name: str):
    def decorate(func):
        ADAPTERS[name] = func
        return func

    return decorate


@dataclass
class DeckData:
    name: str
    sections: dict[str, list[dict]] = field(default_factory=dict)
    source_kind: str = "unknown"
    warnings: list[str] = field(default_factory=list)

    def add(self, section: str, card: dict) -> None:
        self.sections.setdefault(section or "默认", []).append(card)

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
_DOCX_TABLE_HEADERS = {"解释", "说明", "定义", "含义", "描述", "内容"}
_DOCX_HEADER_FIRST = {"概念", "术语", "名称", "字段", "项目", "关键词",
                      "题目", "问题", "主题", "类别", "参数", "属性", "指标", "符号"}


def _docx_heading(text: str) -> str:
    """去掉标题前面的“一、”“1.”等编号，留作子牌组名。"""
    return re.sub(r"^[一二三四五六七八九十百0-9]+[、.．]\s*", "", text).strip() or text


def _docx_point(text: str):
    for pattern in (_DOCX_ITEM_BOLD, _DOCX_ITEM_PLAIN):
        match = pattern.match(text)
        if match:
            return match.group(1).strip(), match.group(2).strip()
    return None


@register("docx-points")
def from_docx_points(source: Path, name: str = "DOCX知识点") -> DeckData:
    """DOCX 知识点：标题 → 子牌组，编号段落/表格行 → 问答，source 用 para/table 定位。"""
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
    for block in iter_docx_blocks(document):
        if block.kind == "paragraph":
            text = block.text.strip()
            if not text:
                continue
            if block.style.lower().startswith("heading") or block.style.startswith("标题"):
                section = _docx_heading(text)
                continue
            point = _docx_point(text)
            if point is None:
                if block.numbered:
                    auto_numbered.append(block.locator)
                continue
            keyword, explanation = point
            deck.add(section, {
                "type": "qa",
                "q": _front(keyword),
                "a": explanation,
                "source": block.locator,
                "tags": ["source:docx", "type:qa"],
            })
            card_count += 1
        elif block.kind == "table_row":
            cells = block.cells
            if len(cells) < 2:
                continue
            # 只有“首格也是表头词”时才丢首行；避免把 ["端口","解释"] 这类真实数据误判为表头。
            if (block.row_index == 1
                    and cells[0] in _DOCX_HEADER_FIRST
                    and cells[1] in _DOCX_TABLE_HEADERS):
                continue
            deck.add(section, {
                "type": "qa",
                "q": cells[0],
                "a": " | ".join(cells[1:]),
                "source": block.locator,
                "tags": ["source:docx", "type:qa"],
            })
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


def write_deck(deck: DeckData, out_dir: str | Path, force: bool = False) -> Path:
    """把适配结果写成 <out>/deck.json + <out>/cards/NN.json。

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
    return out
