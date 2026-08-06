#!/usr/bin/env python3
"""Standalone entry point: generate MQTT Anki deck from MD knowledge points.

Parses data3_mqtt/MQTT_100_Key_Knowledge_Points.md (100 knowledge points in
10 sections). Each knowledge point produces two cards:

1. Basic Q&A card -- front uses the hybrid-mode rule, back is the explanation.
2. Multiple-choice card -- front is the question plus 4 options (A/B/C/D),
   back is the correct answer plus a hint (<= 150 chars).

Usage:
    python3 generate_mqtt.py           # no AI, fast & free
    python3 generate_mqtt.py --ai       # AI distractors + hints (DeepSeek/Claude)

Output:
    output/MQTT协议卡组.apkg  (with summary report)
"""

import argparse
import hashlib
import logging
import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple

import genanki  # type: ignore[import-untyped]

from src.ai_mc_generator import generate_mc_data as ai_generate_mc_data
from src.config import CONFIG
from src.export.anki_exporter import escape_html
from src.models import Flashcard

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("mqtt")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SOURCE_PATH = Path("data3_mqtt/MQTT_100_Key_Knowledge_Points.md")
DECK_NAME = "MQTT协议"
OUTPUT_FILENAME = "MQTT协议卡组.apkg"

MAX_OPTION_LEN = 150
MAX_HINT_LEN = 150

# 定义型术语标记：出现时 front 用 "什么是{关键词}？" 格式
DEFINITION_KEYWORDS = ("全称", "含义", "概念", "定义")

ITEM_PATTERN = re.compile(r"^(\d+)\.\s+\*\*(.+?)\*\*[：:]\s*(.+)")
# 章节标题：## 一、MQTT 基础概念（1-15）。仅在遇到数字范围（如 1-15）时截断，
# 以保留 "主题（Topic）与通配符" 这类中间含括号的完整章节名。
SECTION_PATTERN = re.compile(r"^##\s+[一二三四五六七八九十]+[、.]\s*(.+?)(?:（\d|$)")

# ---------------------------------------------------------------------------
# MQTT-specific genanki model (separate ID range)
# ---------------------------------------------------------------------------

MQTT_BASIC_MODEL_ID = CONFIG.mqtt_basic_model_id
MQTT_PARENT_DECK_ID = CONFIG.mqtt_parent_deck_id

_CSS = """
.card {
    font-family: "PingFang SC", "Noto Sans SC", "Helvetica Neue", sans-serif;
    font-size: 16px;
    line-height: 1.8;
    color: #333;
    padding: 20px;
}
.card.night_mode {
    color: #e0e0e0;
}
.card-front { text-align: left; }
.card-back { text-align: left; }
.question {
    font-size: 18px;
    font-weight: 600;
    color: #1a1a2e;
    margin-bottom: 10px;
}
.night_mode .question { color: #a8d8ea; }
.answer { font-size: 16px; color: #333; line-height: 1.8; }
.night_mode .answer { color: #e0e0e0; }
.source-tag { font-size: 11px; color: #999; margin-top: 5px; }
.source-info {
    font-size: 11px; color: #aaa; margin-top: 10px;
    padding-top: 10px; border-top: 1px solid #eee;
}
.night_mode .source-info { border-top-color: #444; color: #777; }
"""

basic_model = genanki.Model(
    MQTT_BASIC_MODEL_ID,
    "MQTT Q&A",
    fields=[
        {"name": "Question"},
        {"name": "Answer"},
        {"name": "Source"},
        {"name": "Section"},
    ],
    templates=[
        {
            "name": "Card 1",
            "qfmt": """
                <div class="card-front">
                    <div class="question">{{Question}}</div>
                    <div class="source-tag">{{Source}}</div>
                </div>
            """,
            "afmt": """
                <div class="card-back">
                    <div class="question">{{Question}}</div>
                    <hr id="answer">
                    <div class="answer">{{Answer}}</div>
                    <hr>
                    <div class="source-info">
                        <small>来源: {{Source}} | {{Section}}</small>
                    </div>
                </div>
            """,
        }
    ],
    css=_CSS,
)

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class KnowledgePoint:
    """A single MQTT knowledge point parsed from the source MD file."""

    number: int
    keyword: str
    explanation: str
    section: str


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


def _clean_section(section: str) -> str:
    """Shorten a raw section header into a concise tag-friendly name."""
    name = section.strip()
    if name.startswith("MQTT "):
        name = name[5:].strip()
    return name


def parse_md(filepath: Path) -> List[KnowledgePoint]:
    """Parse the MQTT knowledge points MD file into knowledge points."""
    text = filepath.read_text(encoding="utf-8")
    points: List[KnowledgePoint] = []
    current_section = ""

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue

        section_match = SECTION_PATTERN.match(stripped)
        if section_match:
            current_section = _clean_section(section_match.group(1))
            continue

        item_match = ITEM_PATTERN.match(stripped)
        if item_match:
            points.append(
                KnowledgePoint(
                    number=int(item_match.group(1)),
                    keyword=item_match.group(2).strip(),
                    explanation=item_match.group(3).strip(),
                    section=current_section,
                )
            )

    return points


# ---------------------------------------------------------------------------
# Card content helpers
# ---------------------------------------------------------------------------


def build_front(keyword: str) -> str:
    """Build the card front using the hybrid-mode rule.

    Definition-type terms (含全称/含义/概念/定义标记) and short standalone
    concept terms (e.g. 单向认证) become "什么是{关键词}？". Feature,
    enumeration and description terms keep the keyword as-is.
    """
    keyword = keyword.strip()
    if any(marker in keyword for marker in DEFINITION_KEYWORDS):
        return f"什么是{keyword}？"
    if len(keyword) <= 5:
        return f"什么是{keyword}？"
    return keyword


def _truncate(text: str, max_len: int) -> str:
    """Truncate text so it never exceeds max_len characters.

    When truncation is needed the ellipsis replaces the last character, so the
    returned string is at most max_len chars (keeps hints within the ≤150-char
    acceptance criterion).
    """
    text = text.strip()
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rstrip() + "…"


def _make_tags(section: str, card_type: str) -> List[str]:
    """Build card tags from the section name and card type."""
    return ["source:mqtt", "topic:mqtt", f"MQTT::{section}", f"type:{card_type}"]


def _make_card(
    front: str,
    back: str,
    section: str,
    tags: List[str],
    card_type: str,
) -> Flashcard:
    """Create a Flashcard bound to the MQTT deck."""
    return Flashcard(
        front=front,
        back=back,
        deck_name=DECK_NAME,
        source_file=SOURCE_PATH.name,
        source_section=section,
        tags=tags,
        card_type=card_type,
    )


# ---------------------------------------------------------------------------
# AI MC data (delegated to shared module, only when --ai flag is set)
# ---------------------------------------------------------------------------


def _fallback_distractors(
    points: List[KnowledgePoint], index: int, correct: str
) -> List[str]:
    """Build fallback distractors from other points' explanations."""
    distractors: List[str] = []
    seen: set = {correct}
    current_section = points[index].section
    ordered = [p for p in points if p.section == current_section] + [
        p for p in points if p.section != current_section
    ]
    for point in ordered:
        candidate = _truncate(point.explanation, MAX_OPTION_LEN)
        if candidate in seen:
            continue
        seen.add(candidate)
        distractors.append(candidate)
        if len(distractors) >= 3:
            break
    return distractors


# ---------------------------------------------------------------------------
# Card building
# ---------------------------------------------------------------------------


def build_qa_cards(points: List[KnowledgePoint]) -> List[Flashcard]:
    """Build basic Q&A cards, one per knowledge point."""
    cards: List[Flashcard] = []
    for point in points:
        cards.append(
            _make_card(
                front=build_front(point.keyword),
                back=point.explanation,
                section=point.section,
                tags=_make_tags(point.section, "qa"),
                card_type="basic",
            )
        )
    return cards


def _build_mc_front_back(
    question: str,
    correct: str,
    distractors: List[str],
    number: int,
    hint: str,
) -> Tuple[str, str]:
    """Assemble the MC front/back from its parts.

    The correct answer is placed at a deterministic position (number % 4)
    so results are reproducible without randomness.
    """
    correct_position = number % 4
    options: List[Tuple[str, bool]] = []
    slot = 0
    for pos in range(4):
        if pos == correct_position:
            options.append((correct, True))
        else:
            options.append((distractors[slot], False))
            slot += 1

    option_lines = [
        f"{chr(ord('A') + pos)}. {text}" for pos, (text, _) in enumerate(options)
    ]
    front = question + "<br><br>" + "<br>".join(option_lines)

    correct_label = chr(ord("A") + correct_position)
    correct_text = options[correct_position][0]
    back = f"正确答案：{correct_label}. {correct_text}<br><br>扩展：{hint}"
    return front, back


def build_mc_cards(  # pylint: disable=too-many-locals
    points: List[KnowledgePoint], mc_data: Dict[int, Dict[str, Any]]
) -> List[Flashcard]:
    """Build multiple-choice cards, one per knowledge point."""
    cards: List[Flashcard] = []
    for index, point in enumerate(points):
        question = build_front(point.keyword)
        correct = _truncate(point.explanation, MAX_OPTION_LEN)
        ai_item = mc_data.get(point.number, {})

        # Collect candidate distractors (AI first, then fallback fill).
        distractors: List[str] = []
        seen: set = {correct}
        for distractor in ai_item.get("distractors", []):
            candidate = _truncate(distractor, MAX_OPTION_LEN)
            if candidate and candidate not in seen:
                seen.add(candidate)
                distractors.append(candidate)
        if len(distractors) < 3:
            for fallback in _fallback_distractors(points, index, correct):
                if fallback not in seen:
                    seen.add(fallback)
                    distractors.append(fallback)
                if len(distractors) >= 3:
                    break

        distractors = distractors[:3]
        while len(distractors) < 3:
            distractors.append("以上选项都不正确")

        ai_hint = (ai_item.get("hint") or "").strip()
        if not ai_hint:
            ai_hint = (
                f"本题考察「{point.keyword}」，请结合 MQTT 协议整体框架"
                "理解其核心定义与适用场景。"
            )
        hint = _truncate(ai_hint, MAX_HINT_LEN)

        front, back = _build_mc_front_back(
            question, correct, distractors, point.number, hint
        )

        cards.append(
            _make_card(
                front=front,
                back=back,
                section=point.section,
                tags=_make_tags(point.section, "mc"),
                card_type="mc",
            )
        )
    return cards


# ---------------------------------------------------------------------------
# Quality check (lighter than the main pipeline's QualityFilter)
# ---------------------------------------------------------------------------


def basic_quality_check(cards: List[Flashcard]) -> List[Flashcard]:
    """Remove cards that fail basic quality checks."""
    valid: List[Flashcard] = []
    option_labels = [f"{label}. " for label in ("A", "B", "C", "D")]

    for card in cards:
        front = card.front.strip()
        back = card.back.strip()

        if len(front) < 5 or len(back) < 10:
            continue

        if card.card_type == "mc":
            option_count = sum(1 for label in option_labels if label in front)
            if option_count < 4:
                continue
            if "正确答案：" not in back or "扩展：" not in back:
                continue

        valid.append(card)

    dropped = len(cards) - len(valid)
    if dropped:
        log.warning("Quality check dropped %d cards", dropped)
    return valid


# ---------------------------------------------------------------------------
# Export + report
# ---------------------------------------------------------------------------


def _deck_id(deck_name: str) -> int:
    """Generate a deterministic deck ID from the deck name.

    Uses hashlib.md5 instead of built-in hash() so the ID is consistent
    across Python processes (hash() is salted since 3.3).
    """
    digest = hashlib.md5(deck_name.encode("utf-8")).hexdigest()
    return MQTT_PARENT_DECK_ID + int(digest[:8], 16) % (1 << 20)


def _get_deck(deck_name: str, decks: Dict[str, Any]) -> Any:
    """Get or create a genanki deck."""
    if deck_name not in decks:
        decks[deck_name] = genanki.Deck(_deck_id(deck_name), deck_name)
    return decks[deck_name]


def export_cards(cards: List[Flashcard], output_path: Path) -> str:
    """Export cards to an .apkg using the MQTT-specific model."""
    decks: Dict[str, Any] = {}

    for card in cards:
        deck = _get_deck(card.deck_name, decks)
        # 安全转义 HTML：保留 <b>/<br>/<hr>，转义其他 <>
        safe_front = escape_html(card.front)
        safe_back = escape_html(card.back)
        safe_source = escape_html(card.source_file)
        safe_section = escape_html(card.source_section)

        note = genanki.Note(
            model=basic_model,
            fields=[safe_front, safe_back, safe_source, safe_section],
            tags=card.tags,
        )
        deck.add_note(note)

    package = genanki.Package(list(decks.values()))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    package.write_to_file(str(output_path))

    log.info("Exported to %s", output_path)
    for deck_name, deck in sorted(decks.items()):
        log.info("  Deck: %s (%d notes)", deck_name, len(deck.notes))

    return str(output_path)


def _display_text(text: str) -> str:
    """Replace <br> markers with newlines for report readability."""
    return text.replace("<br>", "\n")


def generate_report(cards: List[Flashcard], output_path: Path) -> str:
    """Generate a human-readable summary report."""
    lines: List[str] = []
    lines.append("=" * 60)
    lines.append("MQTT Anki 卡组生成报告")
    lines.append("=" * 60)
    lines.append(f"总卡片数: {len(cards)}")
    lines.append(f"输出文件: {output_path}")
    lines.append("")

    # By section and card type
    section_counts: Dict[str, Dict[str, int]] = {}
    for card in cards:
        counts = section_counts.setdefault(card.source_section, {"basic": 0, "mc": 0})
        counts[card.card_type] = counts.get(card.card_type, 0) + 1

    lines.append("--- 按章节统计 (Q&A / 选择题) ---")
    for section, counts in sorted(section_counts.items()):
        lines.append(
            f"  {section}: Q&A {counts.get('basic', 0)} 张, "
            f"选择题 {counts.get('mc', 0)} 张"
        )

    # By card type
    type_counter = Counter(card.card_type for card in cards)
    lines.append("\n--- 按卡片类型统计 ---")
    for card_type, count in sorted(type_counter.items()):
        lines.append(f"  {card_type}: {count} 张")

    # Sample cards
    lines.append("\n--- 抽样卡片 (前 10 张) ---")
    for index, card in enumerate(cards[:10]):
        lines.append(f"\n卡片 {index + 1}:")
        lines.append(f"  类型: {card.card_type}")
        lines.append(f"  问题: {_display_text(card.front)[:120]}")
        lines.append(f"  答案: {_display_text(card.back)[:120]}")
        lines.append(f"  标签: {', '.join(card.tags)}")
        lines.append(f"  章节: {card.source_section}")

    lines.append("\n" + "=" * 60)
    report = "\n".join(lines)

    report_path = output_path.with_suffix(".txt")
    report_path.write_text(report, encoding="utf-8")
    log.info("Report written to %s", report_path)

    print()
    print(report)
    return report


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():  # pylint: disable=too-many-locals
    """Run the MQTT deck generation pipeline."""
    parser = argparse.ArgumentParser(description="生成 MQTT 协议 Anki 卡组")
    parser.add_argument(
        "--ai",
        action="store_true",
        help="启用 AI 生成选择题干扰项和扩展提示（需配置 API Key）",
    )
    args = parser.parse_args()

    log.info("=" * 50)
    log.info("MQTT Anki 卡组生成器")
    log.info("=" * 50)

    source_path = SOURCE_PATH
    if not source_path.exists():
        log.error("Source file not found: %s", source_path.resolve())
        sys.exit(1)
    log.info("Source: %s (%d bytes)", source_path.name, source_path.stat().st_size)

    # Phase 1: Parse
    log.info("Phase 1: Parsing")
    log.info("-" * 40)
    points = parse_md(source_path)
    sections = sorted({point.section for point in points})
    log.info("  Parsed %d knowledge points in %d sections", len(points), len(sections))
    for section in sections:
        count = sum(1 for point in points if point.section == section)
        log.info("  - %s: %d 条", section, count)

    if not points:
        log.error("No knowledge points parsed")
        sys.exit(1)

    print()

    # Phase 2: AI MC data (only when --ai flag is set)
    log.info("Phase 2: AI 选择题生成")
    log.info("-" * 40)
    mc_data: Dict[int, Dict[str, Any]] = {}
    if args.ai:
        # Determine API provider and key
        if CONFIG.deepseek_api_key:
            provider = "deepseek"
            api_key = CONFIG.deepseek_api_key
            api_model = CONFIG.deepseek_api_model
        elif CONFIG.anthropic_api_key:
            provider = "claude"
            api_key = CONFIG.anthropic_api_key
            api_model = CONFIG.anthropic_api_model
        else:
            log.warning("未配置任何 API Key，选择题干扰项使用 fallback 模式")
            provider = ""
            api_key = ""
            api_model = ""

        if api_key:
            # Convert KnowledgePoint to plain dict for shared module
            points_dicts = [
                {
                    "number": p.number,
                    "keyword": p.keyword,
                    "explanation": p.explanation,
                }
                for p in points
            ]
            mc_data = ai_generate_mc_data(
                points=points_dicts,
                domain="MQTT 协议",
                api_key=api_key,
                api_model=api_model,
                api_provider=provider,
            )
    else:
        log.info("  未启用 --ai，选择题干扰项使用 fallback 模式")
        log.info("  提示：使用 --ai 标志启用 AI 生成高质量干扰项")

    print()

    # Phase 3: Build cards
    log.info("Phase 3: 构建卡片")
    log.info("-" * 40)
    qa_cards = build_qa_cards(points)
    mc_cards = build_mc_cards(points, mc_data)
    log.info("  Q&A 卡片: %d", len(qa_cards))
    log.info("  选择题卡片: %d", len(mc_cards))
    all_cards = qa_cards + mc_cards

    print()

    # Phase 4: Quality check
    log.info("Phase 4: Quality check")
    log.info("-" * 40)
    filtered = basic_quality_check(all_cards)
    log.info("  %d -> %d cards", len(all_cards), len(filtered))

    print()

    # Phase 5: Export
    log.info("Phase 5: Export")
    log.info("-" * 40)
    output_dir = CONFIG.output_dir.resolve()
    output_path = output_dir / OUTPUT_FILENAME
    export_cards(filtered, output_path)

    print()

    generate_report(filtered, output_path)

    log.info("Done! Generated %d cards in %s", len(filtered), output_path)


if __name__ == "__main__":
    main()
