"""plan.json 的契约：校验、编译、对比。

plan.json 是文档抽取的唯一接缝——机械适配器、人手、离线 LLM 都只写它，
再由本模块做**确定性**校验，通过后才编译成牌组目录。这样做的原因见
docs/extraction-policy.md：版面结构不等于知识单元结构，抽取该由能读懂的
一方决定，但「决定」必须有原文证据，且证据能被机器核对。

规则（E 系列，全部确定性，不做语义裁决）：

- E1 quote 必须是定位文本的逐字子串（忽略全部空白差异）
- E2 答案（cloze 用 text/extra）里的每个数字都必须出现在 quote 里；问题里的数字
  多为编号（案例 2、第 4 节），只给 warning 不拦
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
    "locator", "quote", "q", "a", "text", "extra", "type", "kind",
    "tags", "id", "section",
}
#: 卡型：不同文体里值得背的东西不是同一类，验收标准也必须分开。
#: - claim：观点/判断（要能被原文支持）
#: - style：写法/结构/语气（要有足够长的样本才看得出）
#: - phrase：金句（要能整句背下来）
#: - fact：事实/数字（要能核对）
CARD_KINDS = {
    "claim": "观点/判断",
    "style": "写法/结构/语气",
    "phrase": "金句",
    "fact": "事实/数字",
}
CARD_KIND_NAMES = tuple(CARD_KINDS)
PHRASE_MAX_CHARS = 60
STYLE_MIN_CHARS = 30
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
PAGE_LOCATOR_RE = re.compile(r"^page:([1-9]\d*)(?:-([1-9]\d*))?$")
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
    """卡面用于查专名的文本（qa 与 cloze 都覆盖）。"""
    if entry.get("type") == "cloze":
        return f"{entry.get('text', '')} {entry.get('extra', '')}"
    return f"{entry.get('q', '')} {entry.get('a', '')}"


def _answer_text(entry: dict) -> str:
    """卡面用于查数字的文本：只查答案。

    问题里的数字常常是编号（「案例 2」「第 4 节」），不是要背的事实；
    把它们当卡面数字会误报，真实讲义上十有八九都有这种引用。
    """
    if entry.get("type") == "cloze":
        return f"{entry.get('text', '')} {entry.get('extra', '')}"
    return str(entry.get("a") or "")


_LABEL_NUMBER_RE = re.compile(r"(?:案例|第|图|表|章|节|页|步|项)\s*\d+")


def _question_stem(entry: dict) -> str:
    """问题去掉编号类引用后的文本，用于给问题里的数字做软提示。"""
    if entry.get("type") == "cloze":
        return ""
    return _LABEL_NUMBER_RE.sub("", str(entry.get("q") or ""))


def _range_reversed(locator: str) -> bool:
    parsed = parse_plan_locator(locator)
    return parsed is not None and parsed[0] == "page" and parsed[1] > parsed[2]


def _reversed_message(locator: str) -> str:
    parsed = parse_plan_locator(locator) or ("", 0, 0)
    return f"定位区间倒置: {locator}（起点 {parsed[1]} 大于终点 {parsed[2]}）"


def parse_plan_locator(locator: str) -> tuple[str, int, int] | None:
    """plan 的定位：page:N，或 ingest 的 para/line/block/table 定位。"""
    match = PAGE_LOCATOR_RE.fullmatch(locator)
    if match:
        start = int(match.group(1))
        end = int(match.group(2) or start)
        return ("page", start, end)
    return parse_locator(locator)


def locator_text(locator: str, ingest: IngestData) -> str | None:
    """定位对应的原文；不存在返回 None。"""
    parsed = parse_plan_locator(locator)
    if parsed is not None and parsed[0] == "page":
        start, end = parsed[1], parsed[2]
        if start == end:
            return ingest.pages.get(start)
        texts = []
        for number in range(start, end + 1):
            text = ingest.pages.get(number)
            if text is None:
                return None
            texts.append(text)
        return "\n\n".join(texts)
    return ingest.locators.get(locator)


def _overlaps(a: str, b: str) -> bool:
    """两个定位是否相交（同前缀；table 先比表号再比行）。"""
    if a.startswith("chapter:") or b.startswith("chapter:"):
        return a == b
    pa, pb = parse_plan_locator(a), parse_plan_locator(b)
    if pa is None or pb is None or pa[0] != pb[0]:
        return False
    if pa[0] == "page":
        return not (pa[2] < pb[1] or pb[2] < pa[1])
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


def _covered_chars(entries: list[dict], ingest: IngestData) -> int:
    """条目实际读过的原文总字数（按 group 去重，PDF 按页去重）。

    密度的分母是「卡数」，分子必须是「读过的原文」，不是卡片自己那一小段——
    否则一段 70 字的散文出两张卡会被算成 35 字/张，永远报「太密」。
    """
    groups = ingest.groups or []
    if groups:
        total = 0
        for group in groups:
            locator = group.get("locator")
            if not isinstance(locator, str) or not locator:
                continue
            if any(_overlaps(locator, entry["locator"]) for entry in entries):
                total += int(group.get("chars") or 0)
        return total
    if ingest.pages:
        pages: set[int] = set()
        for entry in entries:
            parsed = parse_plan_locator(entry["locator"])
            if parsed is not None and parsed[0] == "page":
                pages.update(range(parsed[1], parsed[2] + 1))
        return sum(len(ingest.pages.get(number) or "") for number in pages)
    return sum(len(locator_text(entry["locator"], ingest) or "") for entry in entries)


def _also_texts(ingest: IngestData) -> tuple[str, list[tuple[str, str]]]:
    """第二份 ingest 的全文与「原子单元」文本，都按忽略空白归一。

    原子单元只取不跨区间的定位（`line:3`、`page:7`、`block:2`），
    区间定位（`line:3-7`）是拼接出来的，用它判断「是否跨单元」会失真。
    """
    if ingest.pages:
        atomic = [(f"page:{number}", _without_space(text or ""))
                  for number, text in sorted(ingest.pages.items())]
        full = "".join(text for _, text in atomic)
        return full, atomic
    atomic = []
    for locator, text in ingest.locators.items():
        if not isinstance(locator, str):
            continue
        tail = locator.split(":", 1)[-1]
        if "-" in tail:          # 区间/表号以外：区间是拼接文本
            continue
        atomic.append((locator, _without_space(text or "")))
    return "".join(text for _, text in atomic), atomic


def _cross_check(entries: list[dict], also: list[IngestData], report: Report,
                 stats: dict, primary_format: str | None = None) -> None:
    """把每张卡的 quote 拿到第二份（第三份…）ingest 里重校一遍。

    用途：同一本书的 epub/pdf/txt 分别 ingest，定位体系不同（chapter:C/p:M、page:N、line:N），
    但正文应当一致。逐字命中说明两份内容相同；找不到说明有改写、缺段或解析差异。
    """
    results: list[dict] = []
    for ingest in also:
        fmt = getattr(ingest, "format", None) or "unknown"
        if primary_format and fmt == primary_format:
            report.add_warning(
                "also", f"第二份 ingest 与主 ingest 同为 {fmt}：交叉校验意义有限，换成另一种格式才能验证")
        full, atomic = _also_texts(ingest)
        hit = miss = split = 0
        for entry in entries:
            if entry["kind"] != "card":
                continue
            quote = _without_space(entry.get("quote") or "")
            if not quote:
                continue
            if quote not in full:
                miss += 1
                report.add_warning(
                    entry["where"],
                    f"在第二份 ingest（{fmt}）里找不到逐字引用：两份文本不一致，"
                    "或被格式改写（引号、全半角、断字）")
            else:
                hit += 1
                if not any(quote in text for _, text in atomic):
                    split += 1
        results.append({"format": fmt, "hit": hit, "miss": miss, "split": split})
        if split:
            report.add_warning(
                "also", f"{split} 张引用在 {fmt} 里要跨单元拼接才命中（换页/换块切断）："
                        "不是文本不一致，但该格式的定位无法单点溯源")
    stats["also"] = results


_CJK_RUN_RE = re.compile(r"[\u4e00-\u9fff]+")
_ASCII_NAME_RE = re.compile(r"\b[A-Z][a-z]{2,}\b")
SPOILER_WINDOW = 6
SPOILER_SAMPLE = 2


def _cjk_windows(text: str, size: int = SPOILER_WINDOW) -> set[str]:
    """中文里长度 6 的连续片段：够长才稀有，普通短语不会误报。"""
    windows: set[str] = set()
    for run in _CJK_RUN_RE.findall(normalize(text)):
        for index in range(len(run) - size + 1):
            windows.add(run[index:index + size])
    return windows


def _novel_index(ingest: IngestData) -> tuple[dict[str, tuple[int, int]], dict[str, tuple[int, int]]]:
    """(六字片段 → 首次出现位置, 拉丁名 → 首次出现位置)，只统计 epub 定位。"""
    windows: dict[str, tuple[int, int]] = {}
    names: dict[str, tuple[int, int]] = {}
    for locator, text in ingest.locators.items():
        parsed = parse_plan_locator(locator) if isinstance(locator, str) else None
        if not parsed or parsed[0] != "epub":
            continue
        key = (parsed[1], parsed[2])
        for window in _cjk_windows(text):
            if window not in windows or key < windows[window]:
                windows[window] = key
        for match in _ASCII_NAME_RE.finditer(text or ""):
            name = match.group(0).lower()
            if name not in names or key < names[name]:
                names[name] = key
    return windows, names


def _spoiler_check(plan: dict, entries: list[dict], ingest: IngestData,
                   report: Report, stats: dict) -> None:
    """小说防剧透。两种确定性信号 + 一种显式声明：

    1. 卡面直接复制了后文才出现的整句（六字以上的连续片段）——warning；
    2. 卡面提到后文才出场的拉丁名（如 Linda）——warning；
    3. plan.entities 里声明的人物/地点，卡面在它登场前提到——error。

    前两条偏保守（宁可漏，不可误报）：只抓逐字复制与拉丁名，
    中文人名的识别需要声明实体才能判，工具不做猜名。
    """
    windows, names = _novel_index(ingest)
    if not windows and not names:
        report.add_warning("spoiler", "novel profile 需要 epub 定位（chapter:C/p:M）；"
                                      "本次 ingest 里没有，跳过剧透检查")
        stats["spoiler"] = {"entities": 0, "windows": 0, "names": 0}
        return

    entities = plan.get("entities") or []
    declared: list[tuple[str, tuple[int, int], str]] = []
    for index, entity in enumerate(entities if isinstance(entities, list) else []):
        where = f"entities[{index}]"
        if not isinstance(entity, dict):
            report.add_error(where, "必须是 {name, locator} 对象")
            continue
        name = str(entity.get("name") or "").strip()
        locator = str(entity.get("locator") or "").strip()
        parsed = parse_plan_locator(locator)
        if not name:
            report.add_error(where, "name 不能为空")
            continue
        if not parsed or parsed[0] != "epub":
            report.add_error(where, f"locator 必须是 chapter:C/p:M，实际为 {locator!r}")
            continue
        declared.append((name, (parsed[1], parsed[2]), locator))

    window_leaks = name_leaks = 0
    for entry in entries:
        if entry["kind"] != "card":
            continue
        parsed = parse_plan_locator(entry["locator"])
        if not parsed or parsed[0] != "epub":
            continue
        position = (parsed[1], parsed[2])
        for name, spot, locator in declared:
            if name in _card_text(entry) and position < spot:
                report.add_error(
                    entry["where"],
                    f"剧透：实体「{name}」在 {locator} 才出场，这张卡在 "
                    f"{entry['locator']} 就提到了它；把它挪到出场之后，或记一条 spoiler 跳过")

        quote_windows = _cjk_windows(entry.get("quote") or "")
        late = [(window, windows[window]) for window in _cjk_windows(_card_text(entry))
                if window in windows and window not in quote_windows
                and windows[window] > position]
        if late:
            window_leaks += 1
            late.sort(key=lambda item: item[1])
            sample = "、".join(f"「{window}」" for window, _ in late[:SPOILER_SAMPLE])
            spot = late[0][1]
            report.add_warning(
                entry["where"],
                f"卡面复制了后文才出现的句子：{sample}（最早 chapter:{spot[0]}/p:{spot[1]}）；"
                "小说按顺序读，这里会提前泄露情节")

        card_names = {match.group(0).lower() for match in _ASCII_NAME_RE.finditer(_card_text(entry))}
        late_names = [(name, names[name]) for name in card_names
                      if name in names and names[name] > position]
        if late_names:
            name_leaks += 1
            late_names.sort(key=lambda item: item[1])
            name, spot = late_names[0]
            report.add_warning(
                entry["where"],
                f"卡面提到后文才出场的名字「{name}」（chapter:{spot[0]}/p:{spot[1]} 才出现）")
    stats["spoiler"] = {"entities": len(declared), "windows": window_leaks,
                        "names": name_leaks}


NOVEL_SKIP_REASONS = ("plot_summary", "spoiler", "character_note")
MAX_QUOTE_CHARS_NOVEL = 800

# 散文集/随笔：一段完整论述常常超过 300 字，跳过理由也和小说不同
# （「这段只是轶事」「这段是文风示范」「这段是背景铺垫」才是真正的理由）。
ESSAY_SKIP_REASONS = ("anecdote", "style_note", "background")
MAX_QUOTE_CHARS_ESSAY = 800

PROFILES = {
    "manual": {"quote_max": MAX_QUOTE_CHARS, "reasons": ()},
    "novel": {"quote_max": MAX_QUOTE_CHARS_NOVEL, "reasons": NOVEL_SKIP_REASONS},
    "essay": {"quote_max": MAX_QUOTE_CHARS_ESSAY, "reasons": ESSAY_SKIP_REASONS},
}
PROFILE_NAMES = tuple(PROFILES)

# 密度带：平均多少字原文支撑一张卡。太密＝在硬拆信息，太疏＝漏了值得出的内容。
# 只做提示（warning），不拦编译：密度是启发式，最终由人判断。
DENSITY_BANDS = {
    "manual": (200, 700),
    "novel": (400, 1200),
    "essay": (600, 1600),
}
DENSITY_NAMES = tuple(DENSITY_BANDS)
MANUAL_FACT_SHARE_MIN = 0.3


def _profile_quote_max(profile: str | None) -> int:
    return PROFILES.get(profile or "manual", PROFILES["manual"])["quote_max"]


def _allowed_reasons(profile: str | None) -> tuple[str, ...]:
    return PLAN_SKIP_REASONS + PROFILES.get(
        profile or "manual", PROFILES["manual"])["reasons"]


def check_plan(plan: dict, ingest: IngestData,
               min_coverage: float | None = None,
               profile: str | None = None,
               density: str | None = None,
               density_min: int | None = None,
               density_max: int | None = None,
               also: list[IngestData] | None = None) -> tuple[Report, dict]:
    """校验 plan；返回 (报告, 统计)。有 error 时不应编译。"""
    report = Report()
    stats: dict = {"cards": 0, "skipped": 0, "groups": len(ingest.groups or []),
                   "covered": 0, "coverage": None, "kinds": {}}

    if profile is not None and profile not in PROFILES:
        report.add_error("profile", f"必须是 {'/'.join(PROFILE_NAMES)} 之一，实际为 {profile!r}")

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
        if _range_reversed(locator):
            report.add_error(f"{where}.locator", _reversed_message(locator))
            continue
        text = locator_text(locator, ingest)
        if text is None:
            report.add_error(f"{where}.locator", f"定位不在 ingest 产物中: {locator}")
            continue
        if not text.strip():
            report.add_error(f"{where}.locator", f"定位在 ingest 产物中没有文本: {locator}")
            continue
        entries.append({
            "kind": "card", "locator": locator, "where": where,
            "quote": entry.get("quote") if isinstance(entry.get("quote"), str) else "",
            # 卡面文本供剧透检查使用：q/a 或 cloze 的 text/extra
            "q": entry.get("q"), "a": entry.get("a"),
            "text": entry.get("text"), "extra": entry.get("extra"),
            "card_kind": entry.get("kind"),
        })

        key = entry.get("key")
        if key is not None and (not isinstance(key, str) or not CARD_KEY_RE.fullmatch(key)):
            report.add_error(f"{where}.key",
                             f"必须是 12 位小写十六进制字符串（当前 {key!r}）")

        quote = entry.get("quote")
        if not isinstance(quote, str) or not quote.strip():
            report.add_error(f"{where}.quote", "必填：每张卡都要有原文引用")
        else:
            quote_norm = normalize(quote)
            max_quote = _profile_quote_max(profile)
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
            for number in _numbers(_answer_text(entry)):
                if number not in quote_numbers:
                    report.add_error(
                        f"{where}",
                        f"答案数字 {number} 在 quote 里找不到：数字必须来自原文引用")
            for number in _numbers(_question_stem(entry)):
                if number not in quote_numbers:
                    report.add_warning(
                        f"{where}.q",
                        f"问题里的数字 {number} 不在 quote 中；如果是编号可以忽略")
            for identifier in _IDENTIFIER_RE.findall(_card_text(entry)):
                if identifier not in quote_norm and identifier not in full_text:
                    report.add_warning(
                        f"{where}",
                        f"卡面专名 {identifier!r} 既不在 quote 也不在全文中（疑似自造）")

            card_kind = entry.get("kind")
            if card_kind is None:
                report.add_warning(
                    f"{where}.kind",
                    f"建议标注卡型：{'/'.join(CARD_KIND_NAMES)}；不同卡型的验收标准不同")
            elif card_kind not in CARD_KINDS:
                report.add_error(
                    f"{where}.kind",
                    f"必须是 {'/'.join(CARD_KIND_NAMES)} 之一，实际为 {card_kind!r}")
            elif card_kind == "phrase" and len(quote_norm) > PHRASE_MAX_CHARS:
                report.add_warning(
                    f"{where}.quote",
                    f"金句卡的 quote 有 {len(quote_norm)} 字（上限 {PHRASE_MAX_CHARS}）："
                    "太长的引用背不下来，挑能整句记住的那一句")
            elif card_kind == "style" and len(quote_norm) < STYLE_MIN_CHARS:
                report.add_warning(
                    f"{where}.quote",
                    f"文风卡的 quote 只有 {len(quote_norm)} 字（建议 ≥{STYLE_MIN_CHARS}）："
                    "样本太短看不出写法")
            elif card_kind == "fact" and not _numbers(quote_norm) \
                    and not re.search(r"[〇零一二三四五六七八九十百千万亿]+(?:年|月|日|人|次|个|种|倍|万|亿)", quote_norm):
                report.add_warning(
                    f"{where}.quote",
                    "事实卡的 quote 里没有数字或日期：没有可核对锚点的事实容易写错")
            elif card_kind == "claim" and not re.search(r"[？?]\s*$", str(entry.get("q") or "")):
                report.add_warning(
                    f"{where}.q", "观点卡的问题建议写成问句（以 ？ 结尾）")

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
        card_kind = entry.get("kind")
        if isinstance(card_kind, str) and card_kind:
            stats["kinds"][card_kind] = stats["kinds"].get(card_kind, 0) + 1

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
        if _range_reversed(locator):
            report.add_error(f"{where}.locator", _reversed_message(locator))
            continue
        if locator_text(locator, ingest) is None:
            report.add_error(f"{where}.locator", f"定位不在 ingest 产物中: {locator}")
            continue
        reason = entry.get("reason")
        allowed = _allowed_reasons(profile)
        if reason not in allowed:
            report.add_error(
                f"{where}.reason",
                f"必须是 {'/'.join(allowed)} 之一，实际为 {reason!r}")
        entries.append({"kind": "skip", "locator": locator, "where": where})

    def quote_span(entry: dict) -> tuple[int, int] | None:
        """引用在定位文本中的位置（忽略空白），用于判断同段多卡是否各说各话。"""
        quote = _without_space(entry.get("quote") or "")
        text = _without_space(locator_text(entry["locator"], ingest) or "")
        index = text.find(quote) if quote else -1
        if index < 0:
            return None
        return index, index + len(quote)

    for i, left in enumerate(entries):
        for right in entries[i + 1:]:
            # 页码是粗粒度定位：同一页出多张卡是正常的，不参与互斥检查。
            if left["locator"].startswith("page:") or right["locator"].startswith("page:"):
                continue
            if not _overlaps(left["locator"], right["locator"]):
                continue
            if left["kind"] == "card" and right["kind"] == "card":
                span_a, span_b = quote_span(left), quote_span(right)
                if span_a and span_b and (span_a[1] <= span_b[0] or span_b[1] <= span_a[0]):
                    continue
                report.add_error(
                    f"{right['where']}",
                    f"与 {left['where']}（{left['locator']}）的引用重叠："
                    "同一段可以出多张卡，但 quote 必须是不重叠的不同句子")
            elif left["kind"] == "skip" and right["kind"] == "skip":
                report.add_error(
                    f"{right['where']}",
                    f"与 {left['where']}（{left['locator']}）区间相交："
                    "同一段原文只能记一次未出卡")
            else:
                report.add_warning(
                    f"{right['where']}",
                    f"与 {left['where']}（{left['locator']}）区间相交："
                    "同一段里既出了卡又记为未出卡，确认不是重复记账")

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
        covered_pages: set[int] = set()
        for entry in entries:
            parsed = parse_plan_locator(entry["locator"])
            if parsed is not None and parsed[0] == "page":
                covered_pages.update(range(parsed[1], parsed[2] + 1))
        covered_pages &= set(ingest.pages)
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

    if profile == "novel":
        _spoiler_check(plan, entries, ingest, report, stats)

    if also:
        _cross_check(entries, also, report, stats,
                     getattr(ingest, "format", None))

    if density is not None:
        if density not in DENSITY_BANDS:
            report.add_error(
                "density", f"必须是 {'/'.join(DENSITY_NAMES)} 之一，实际为 {density!r}")
        else:
            low, high = DENSITY_BANDS[density]
            if density_min is not None:
                low = density_min
            if density_max is not None:
                high = density_max
            if low > high:
                report.add_error("density", f"下限 {low} 大于上限 {high}")
            else:
                chars = _covered_chars(entries, ingest)
                cards = stats["cards"]
                per_card = round(chars / cards, 1) if cards and chars else None
                stats["density"] = {"profile": density, "min": low, "max": high,
                                    "chars": chars, "cards": cards,
                                    "chars_per_card": per_card}
                if per_card is not None:
                    if per_card < low:
                        report.add_warning(
                            "density",
                            f"平均 {per_card:.0f} 字/张，密于 {density} 口径的 "
                            f"{low}–{high}：可能把信息硬拆成了卡片")
                    elif per_card > high:
                        report.add_warning(
                            "density",
                            f"平均 {per_card:.0f} 字/张，疏于 {density} 口径的 "
                            f"{low}–{high}：可能漏了值得出的内容，或整段只做了概括")
                kinds = stats["kinds"]
                total_kinds = sum(kinds.values())
                if density == "essay" and kinds.get("fact"):
                    report.add_warning(
                        "density",
                        f"散文口径下出现了 {kinds['fact']} 张 fact 卡："
                        "这类文本没有可检验的事实，应换成 claim/style/phrase")
                if density == "manual" and total_kinds:
                    share = kinds.get("fact", 0) / total_kinds
                    if share < MANUAL_FACT_SHARE_MIN:
                        report.add_warning(
                            "density",
                            f"手册口径下 fact 只占 {share:.0%}（建议 ≥"
                            f"{MANUAL_FACT_SHARE_MIN:.0%}）：考点型资料应以可核对的事实为主")

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
        parsed = parse_plan_locator(entry["locator"])
        if parsed is not None and parsed[0] == "page":
            start, end = parsed[1], parsed[2]
            card = {"pages": [start] if start == end else [start, end],
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
        tags = list(entry.get("tags") or [])
        card_kind = entry.get("kind")
        if isinstance(card_kind, str) and card_kind:
            kind_tag = f"kind:{card_kind}"
            if kind_tag not in tags:
                tags.append(kind_tag)
        if tags:
            card["tags"] = tags
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
                 profile: str | None = None,
                 density: str | None = None,
                 density_min: int | None = None,
                 density_max: int | None = None,
                 also: list[IngestData] | None = None) -> tuple[Report, dict, Path | None]:
    """校验通过才写牌组；返回 (报告, 统计, 输出目录或 None)。"""
    report, stats = check_plan(plan, ingest, min_coverage=min_coverage,
                               profile=profile, density=density,
                               density_min=density_min, density_max=density_max,
                               also=also)
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
