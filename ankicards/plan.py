"""plan.json 的契约：校验、编译、对比。

plan.json 是文档抽取的唯一接缝——机械适配器、人手、离线 LLM 都只写它，
再由本模块做**确定性**校验，通过后才编译成牌组目录。这样做的原因见
docs/extraction-policy.md：版面结构不等于知识单元结构，抽取该由能读懂的
一方决定，但「决定」必须有原文证据，且证据能被机器核对。

规则（E 系列，全部确定性，不做语义裁决）：

- E1 quote 必须是定位文本的逐字子串（忽略全部空白差异）
- E2 卡面（q/a，cloze 用 text/extra）里的每个数字都必须出现在 quote 里
- E3 quote 长度 8–300 字：太短不像证据，太长等于把整段抄进卡
- E4 定位必须存在于 ingest 产物中，且该定位有文本
- E5 未出卡理由必须属于枚举；任意两个条目（卡 + 未出卡）的区间不得相交
- E6 覆盖率 = 被条目覆盖的 group 数 / group 总数，低于阈值报 error
- E7 卡面里的 ASCII 专名（标识符）若既不在 quote 也不在全文，给 warning

quote 只活在 plan.json 里，不写进 cards/*.json——Anki 卡面字段是固定的，
plan.json 才是「这张卡从哪句话来」的审计记录。
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

from .adapters import DeckData, SKIP_REASONS, write_deck
from .errors import CardError
from .ingest import IngestData
from .schema import (CARD_KEY_RE, Report, SOURCE_KINDS, load_json, load_spec,
                     parse_locator)

PLAN_VERSION = 1
MIN_QUOTE_CHARS = 8
MAX_QUOTE_CHARS = 300
#: plan 允许的字段。多出来的字段不报错但会 warning，避免拼写错误被静默吞掉。
PLAN_CARD_FIELDS = {
    "locator", "quote", "q", "a", "text", "extra", "type",
    "tags", "id", "section",
}
#: 未出卡理由 = 适配器的机械理由 + 需要读原文才能下的判断。
PLAN_SKIP_REASONS = tuple(SKIP_REASONS) + (
    "step_not_concept",     # 这是操作步骤，不是概念/事实
    "cross_reference",      # 只有「见第 N 节」这类指路
    "merged_into",          # 已并入另一张卡，避免重复
    "low_value",            # 读懂了，但不值得做成记忆卡
    "out_of_scope",         # 不在本次主题范围内
    "unreadable",           # 原文残缺/排版坏了，读不出来
)
_NUMBER_RE = re.compile(r"\d+(?:\.\d+)?")
#: PDF 源没有 para/line/block 定位，plan 用 page:N 指向整页文本。
PAGE_LOCATOR_RE = re.compile(r"^page:[1-9]\d*$")
_IDENTIFIER_RE = re.compile(r"[A-Za-z][A-Za-z0-9_.:/@-]{1,}")


def normalize(text: object) -> str:
    """折叠空白，用于展示与长度判断。"""
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _without_space(text: object) -> str:
    """删除全部空白：PDF/Word 的换行会把空格插在任意位置，逐字比较必须先抹掉空白。"""
    return re.sub(r"\s+", "", str(text or ""))


def _numbers(text: object) -> list[str]:
    """取数字做比对：千分位逗号不算内容差异（2,500 与 2500 是同一个数）。"""
    purified = re.sub(r"(?<=\d),(?=\d)", "", str(text or ""))
    return _NUMBER_RE.findall(purified)


def load_plan(path: str | Path) -> dict:
    """读 plan.json；形状错误抛 CardError（退出码 2）。"""
    data = load_json(Path(path))
    if not isinstance(data, dict):
        raise CardError(f"{path}: plan 顶层必须是对象")
    return data


def _card_text(entry: dict) -> str:
    """卡面用于查数字/专名的文本（qa 与 cloze 都覆盖）。"""
    if entry.get("type") == "cloze":
        return f"{entry.get('text', '')} {entry.get('extra', '')}"
    return f"{entry.get('q', '')} {entry.get('a', '')}"


def parse_plan_locator(locator: str) -> tuple[str, int, int] | None:
    """plan 的定位：page:N，或 ingest 的 para/line/block/table 定位。"""
    if PAGE_LOCATOR_RE.fullmatch(locator):
        number = int(locator.split(":", 1)[1])
        return ("page", number, number)
    return parse_locator(locator)


def locator_text(locator: str, ingest: IngestData) -> str | None:
    """定位对应的原文；不存在返回 None。"""
    if PAGE_LOCATOR_RE.fullmatch(locator):
        return ingest.pages.get(int(locator.split(":", 1)[1]))
    return ingest.locators.get(locator)


def _overlaps(a: str, b: str) -> bool:
    """两个定位是否相交（同前缀；table 先比表号再比行）。"""
    if a.startswith("chapter:") or b.startswith("chapter:"):
        return a == b
    pa, pb = parse_plan_locator(a), parse_plan_locator(b)
    if pa is None or pb is None or pa[0] != pb[0]:
        return False
    if pa[0] == "page":
        return pa[1] == pb[1]
    if pa[0] == "table":
        return pa[1] == pb[1] and not (pa[2] < pb[2] or pb[2] < pa[2])
    return not (pa[2] < pb[1] or pb[2] < pa[1])


def _group_coverage(entries: list[dict], groups: list[dict]) -> tuple[int, list[str]]:
    """算有多少个 group 至少被一个条目碰到；返回 (covered, 未覆盖的 group 定位)。"""
    if not groups:
        return 0, []
    covered = 0
    uncovered: list[str] = []
    for group in groups:
        locator = group.get("locator")
        if not isinstance(locator, str) or not locator:
            continue
        if any(_overlaps(locator, entry["locator"]) for entry in entries):
            covered += 1
        else:
            uncovered.append(locator)
    return covered, uncovered


NOVEL_SKIP_REASONS = ("plot_summary", "spoiler", "character_note")
MAX_QUOTE_CHARS_NOVEL = 800


def check_plan(plan: dict, ingest: IngestData,
               min_coverage: float | None = None,
               profile: str | None = None) -> tuple[Report, dict]:
    """校验 plan；返回 (报告, 统计)。有 error 时不应编译。"""
    report = Report()
    stats: dict = {"cards": 0, "skipped": 0, "groups": len(ingest.groups or []),
                   "covered": 0, "coverage": None}

    if plan.get("version") != PLAN_VERSION:
        report.add_error("version", f"必须是 {PLAN_VERSION}，实际为 {plan.get('version')!r}")

    deck_info = plan.get("deck")
    if not isinstance(deck_info, dict):
        report.add_error("deck", "缺少 deck 对象（name / source_kind）")
        deck_name = "PLAN"
    else:
        deck_name = str(deck_info.get("name") or "").strip()
        if not deck_name:
            report.add_error("deck.name", "牌组名不能为空")
        source_kind = deck_info.get("source_kind")
        if source_kind not in SOURCE_KINDS or source_kind == "unknown":
            report.add_error("deck.source_kind",
                             f"必须是 {sorted(SOURCE_KINDS - {'unknown'})} 之一，实际为 {source_kind!r}")

    cards = plan.get("cards")
    skipped = plan.get("skipped", [])
    if not isinstance(cards, list):
        report.add_error("cards", "必须是数组")
        cards = []
    if not isinstance(skipped, list):
        report.add_error("skipped", "必须是数组")
        skipped = []
    if not cards and not skipped:
        report.add_error(
            "cards", "plan 里既没有卡片也没有未出卡记录：至少要把看过的每段记下来")
    elif not cards:
        report.add_warning(
            "cards", "没有卡片：确认这份资料确实没有值得背的内容（全部记在 skipped）")
    stats["cards"], stats["skipped"] = len(cards), len(skipped)

    full_text = normalize("\n".join(ingest.locators.values()))
    entries: list[dict] = []
    card_ids: set[str] = set()

    for index, entry in enumerate(cards):
        where = f"cards[{index}]"
        if not isinstance(entry, dict):
            report.add_error(where, "必须是对象")
            continue
        for key in sorted(set(entry) - PLAN_CARD_FIELDS):
            report.add_warning(where, f"未知字段 {key!r}（拼错了？）")

        locator = entry.get("locator")
        if not isinstance(locator, str) or not locator:
            report.add_error(f"{where}.locator", "必填")
            continue
        if parse_plan_locator(locator) is None:
            report.add_error(f"{where}.locator", f"不是合法定位: {locator!r}")
            continue
        text = locator_text(locator, ingest)
        if text is None:
            report.add_error(f"{where}.locator", f"定位不在 ingest 产物中: {locator}")
            continue
        if not text.strip():
            report.add_error(f"{where}.locator", f"定位在 ingest 产物中没有文本: {locator}")
            continue
        entries.append({"kind": "card", "locator": locator, "where": where})

        key = entry.get("key")
        if key is not None and (not isinstance(key, str) or not CARD_KEY_RE.fullmatch(key)):
            report.add_error(f"{where}.key",
                             f"必须是 12 位小写十六进制字符串（当前 {key!r}）")

        quote = entry.get("quote")
        if not isinstance(quote, str) or not quote.strip():
            report.add_error(f"{where}.quote", "必填：每张卡都要有原文引用")
        else:
            quote_norm = normalize(quote)
            max_quote = MAX_QUOTE_CHARS_NOVEL if profile == "novel" else MAX_QUOTE_CHARS
            if not (MIN_QUOTE_CHARS <= len(quote_norm) <= max_quote):
                report.add_error(
                    f"{where}.quote",
                    f"长度必须在 {MIN_QUOTE_CHARS}–{max_quote} 字之间，"
                    f"实际 {len(quote_norm)} 字")
            if quote_norm and _without_space(quote_norm) not in _without_space(text):
                report.add_error(
                    f"{where}.quote",
                    f"不是 {locator} 文本的逐字子串（空白差异已忽略）；"
                    "引用必须从原文复制，不能改写")
            quote_numbers = _numbers(quote_norm)
            for number in _numbers(_card_text(entry)):
                if number not in quote_numbers:
                    report.add_error(
                        f"{where}",
                        f"卡面数字 {number} 在 quote 里找不到：数字必须来自原文引用")
            for identifier in _IDENTIFIER_RE.findall(_card_text(entry)):
                if identifier not in quote_norm and identifier not in full_text:
                    report.add_warning(
                        f"{where}",
                        f"卡面专名 {identifier!r} 既不在 quote 也不在全文中（疑似自造）")

        card_type = entry.get("type", "qa")
        if card_type not in ("qa", "cloze"):
            report.add_error(f"{where}.type", f"必须是 qa/cloze，实际为 {card_type!r}")
        elif card_type == "cloze":
            if not str(entry.get("text") or "").strip():
                report.add_error(f"{where}.text", "cloze 卡必须有 text")
        else:
            for key in ("q", "a"):
                if not str(entry.get(key) or "").strip():
                    report.add_error(f"{where}.{key}", "qa 卡必须有非空 q 和 a")

        card_id = entry.get("id")
        if card_id is not None:
            if not isinstance(card_id, str) or not card_id.strip():
                report.add_error(f"{where}.id", "必须是字符串")
            elif card_id in card_ids:
                report.add_error(f"{where}.id", f"id 重复: {card_id}")
            else:
                card_ids.add(card_id)

    for index, entry in enumerate(skipped):
        where = f"skipped[{index}]"
        if not isinstance(entry, dict):
            report.add_error(where, "必须是对象")
            continue
        locator = entry.get("locator")
        if not isinstance(locator, str) or not locator:
            report.add_error(f"{where}.locator", "必填")
            continue
        if parse_plan_locator(locator) is None:
            report.add_error(f"{where}.locator", f"不是合法定位: {locator!r}")
            continue
        if locator_text(locator, ingest) is None:
            report.add_error(f"{where}.locator", f"定位不在 ingest 产物中: {locator}")
            continue
        reason = entry.get("reason")
        allowed = PLAN_SKIP_REASONS + (NOVEL_SKIP_REASONS if profile == "novel" else ())
        if reason not in allowed:
            report.add_error(
                f"{where}.reason",
                f"必须是 {'/'.join(allowed)} 之一，实际为 {reason!r}")
        entries.append({"kind": "skip", "locator": locator, "where": where})

    for i, left in enumerate(entries):
        for right in entries[i + 1:]:
            # 页码是粗粒度定位：同一页出多张卡是正常的，不参与互斥检查。
            if left["locator"].startswith("page:") or right["locator"].startswith("page:"):
                continue
            if _overlaps(left["locator"], right["locator"]):
                report.add_error(
                    f"{right['where']}",
                    f"与 {left['where']}（{left['locator']}）区间相交："
                    f"{left['locator']} 与 {right['locator']}；"
                    "同一段原文只能有一个归属")

    groups = ingest.groups or []
    if groups:
        covered, uncovered = _group_coverage(entries, groups)
        stats["covered"], stats["groups"] = covered, len(groups)
        stats["coverage"] = covered / len(groups)
        if min_coverage is not None and stats["coverage"] < min_coverage:
            sample = "、".join(uncovered[:5])
            report.add_error(
                "coverage",
                f"{covered}/{len(groups)} 个分组被覆盖（{stats['coverage']:.0%}），"
                f"低于阈值 {min_coverage:.0%}；未覆盖：{sample}")
    elif ingest.pages:
        total = len(ingest.pages)
        covered_pages = {int(entry["locator"].split(":", 1)[1]) for entry in entries
                         if entry["locator"].startswith("page:")}
        stats["groups"], stats["covered"] = total, len(covered_pages)
        stats["coverage"] = len(covered_pages) / total if total else None
        if min_coverage is not None and stats["coverage"] is not None \
                and stats["coverage"] < min_coverage:
            report.add_error(
                "coverage",
                f"{len(covered_pages)}/{total} 页被覆盖（{stats['coverage']:.0%}），"
                f"低于阈值 {min_coverage:.0%}：PDF 按页码算覆盖率，"
                "只覆盖部分页面时不要设过高的 --min-coverage")
    elif min_coverage is not None:
        report.add_warning(
            "coverage", "ingest 产物既没有 groups 也没有页面，无法计算覆盖率")

    return report, stats


def derive_key(deck_name: str, source_kind: str, locator: str, seq: int) -> str:
    """稳定身份 key：只由牌组 + 来源类型 + 定位 + 同定位内的序号决定，与卡面文字无关。

    同一段原文重跑 plan（哪怕修了措辞），生成的 key 不变，Anki 里就是同一张卡。
    代价：同一页/同一段里新增或调整卡片顺序会改变后续 key —— 这是有意的显式代价。
    """
    seed = f"{deck_name}|{source_kind}|{locator}|{seq}"
    return hashlib.sha1(seed.encode("utf-8")).hexdigest()[:12]


def build_deck(plan: dict, ingest: IngestData, with_key: bool = False) -> DeckData:
    """把已校验的 plan 变成 DeckData；不写盘，方便复用与测试。"""
    deck_info = plan.get("deck") or {}
    name = str(deck_info.get("name") or "PLAN")
    deck = DeckData(name=name, source_kind=str(deck_info.get("source_kind") or "unknown"))
    seq_by_locator: dict[str, int] = {}
    for entry in plan.get("cards", []):
        locator = entry["locator"]
        key = entry.get("key")
        if not key and with_key:
            seq = seq_by_locator.get(locator, 0)
            seq_by_locator[locator] = seq + 1
            key = derive_key(name, deck.source_kind, locator, seq)
        if entry["locator"].startswith("page:"):
            card = {"pages": [int(entry["locator"].split(":", 1)[1])],
                    "type": entry.get("type", "qa")}
        else:
            card = {"source": entry["locator"], "type": entry.get("type", "qa")}
        if card["type"] == "cloze":
            card["text"] = entry["text"]
            if entry.get("extra"):
                card["extra"] = entry["extra"]
        else:
            card["q"] = entry["q"]
            card["a"] = entry["a"]
        if entry.get("tags"):
            card["tags"] = list(entry["tags"])
        if entry.get("id"):
            card["id"] = entry["id"]
        if key:
            card["key"] = key
        section = str(entry.get("section") or name)
        deck.add_checked(section, card, unit_text=locator_text(entry["locator"], ingest) or "")
    for entry in plan.get("skipped", []):
        # reason 已在 check_plan 里对 PLAN_SKIP_REASONS 校验过，这里直接记账；
        # DeckData.skip 只认适配器的机械理由，拦不下「读过之后的判断」。
        deck.skipped.append({"locator": entry["locator"],
                             "reason": entry["reason"],
                             "note": entry.get("note", "")})
    return deck


def compile_plan(plan: dict, ingest: IngestData, out: str | Path,
                 force: bool = False,
                 min_coverage: float | None = None,
                 with_key: bool = False,
                 profile: str | None = None) -> tuple[Report, dict, Path | None]:
    """校验通过才写牌组；返回 (报告, 统计, 输出目录或 None)。"""
    report, stats = check_plan(plan, ingest, min_coverage=min_coverage,
                               profile=profile)
    if not report.ok:
        return report, stats, None
    if not plan.get("cards"):
        raise CardError("plan 里没有卡片：没有值得背的内容就不要编译牌组，"
                        "skipped 记录本身已经说明看过哪些段落")
    deck = build_deck(plan, ingest, with_key=with_key)
    return report, stats, write_deck(deck, out, force=force)


def _identity(card: dict) -> tuple[str, str, str]:
    if card.get("type") == "cloze":
        return ("cloze", normalize(card.get("text")), normalize(card.get("extra")))
    return ("qa", normalize(card.get("q")), normalize(card.get("a")))


def _label(card: dict) -> str:
    text = card.get("text") or card.get("q") or ""
    return normalize(text)[:40]


def diff_plan(plan: dict, deck_dir: str | Path) -> dict:
    """对比 plan 与已写出的牌组：新增/删除/改动（按归一后的卡面文本比对）。

    只回答「这次会变什么」，不判对错：plan 重跑后哪些卡是新身份，是 Anki 里
    增删卡的直接依据。
    """
    spec = load_spec(Path(deck_dir))
    deck_cards = [card for _, _, card in spec.iter_cards()]
    plan_cards: list[dict] = []
    for entry in plan.get("cards", []):
        if not isinstance(entry, dict):
            continue
        card = {"type": entry.get("type", "qa"),
                "q": entry.get("q"), "a": entry.get("a"),
                "text": entry.get("text"), "extra": entry.get("extra")}
        card["source"] = entry.get("locator", "")
        if str(entry.get("locator", "")).startswith("page:"):
            card["pages"] = [int(str(entry["locator"]).split(":", 1)[1])]
        plan_cards.append(card)

    planned = {_identity(card) for card in plan_cards}
    existing = {_identity(card) for card in deck_cards}
    added = [card for card in plan_cards if _identity(card) not in existing]
    removed = [card for card in deck_cards if _identity(card) not in planned]

    def card_locator(card: dict) -> str:
        pages = card.get("pages")
        if isinstance(pages, list) and pages:
            return f"page:{pages[0]}"
        return str(card.get("source", ""))

    plan_by_loc: dict[str, list[dict]] = {}
    deck_by_loc: dict[str, list[dict]] = {}
    for card in plan_cards:
        plan_by_loc.setdefault(card_locator(card), []).append(card)
    for card in deck_cards:
        deck_by_loc.setdefault(card_locator(card), []).append(card)
    changed = []
    for locator, cards in plan_by_loc.items():
        old = deck_by_loc.get(locator)
        if old is None:
            continue
        if {_identity(card) for card in cards} != {_identity(card) for card in old}:
            changed.append({"locator": locator,
                            "was": [_label(card) for card in old],
                            "now": [_label(card) for card in cards]})
    return {
        "planned": len(plan_cards),
        "existing": len(deck_cards),
        "added": [{"locator": card_locator(card), "text": _label(card)} for card in added],
        "removed": [{"locator": card_locator(card), "text": _label(card)} for card in removed],
        "changed": changed,
    }
