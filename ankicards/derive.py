"""从已写出的牌组派生第二层卡：填空题与选择题。

设计约束（与 plan.py 同一套哲学）：

- 派生卡不重新读原文，只消费已发布的牌组；每张卡必须能指回一张源卡。
- 工具只做可判定的事：逐字锚定、结构、去重、来源；不做价值判断。
- 不调用模型。LLM 只能在外部把候选写进 plan，校验仍走这里。
- 编译写到独立目录，源牌组只读。

关键概念：
    source_key   源卡的稳定身份：有 key 用 key，否则用 Anki guid 现算。
    excerpt      源卡答案里的**逐字片段**（去 HTML 后）。长答案靠选片段，
                 而不是摘要改写成短答案——这是与"生成式出题"的分界线。
"""

from __future__ import annotations

import hashlib
import html
import re
from dataclasses import dataclass, field
from pathlib import Path

from .adapters import DeckData, write_deck
from .errors import CardError
from .ingest import IngestData
from .schema import DeckSpec, Report, identity_seed

DERIVED_VERSION = 1

SKIP_REASONS = (
    "answer_too_long",
    "answer_too_short",
    "no_cloze_span",
    "not_enough_distractors",
    "ambiguous_answer",
    "image_card",
    "duplicate",
    "code_snippet",
)

CHOICE_KINDS = ("fact", "procedure")
DISTRACTOR_SOURCES = ("same-deck", "local", "hybrid", "none")
SOURCE_MODES = ("short", "full", "off")

MIN_ANSWER_CHARS = 8
MAX_CLOZE_TEXT = 160
MIN_CLOZE_SPAN = 2
MAX_CLOZE_SPAN = 20
MIN_OPTION_CHARS = 2
MAX_OPTION_CHARS = 60
OPTION_SIMILARITY = 0.85
MIN_LENGTH_RATIO = 0.4
MAX_LENGTH_RATIO = 2.5
PHRASE_SIMILARITY = 0.9

BANNED_OPTIONS = ("以上都", "全部", "都不对", "以上都不", "以上均", "都正确", "都错")

CODE_MARKERS = ("```", "{{", "}}", "//", "  ", "();", "(){", "};", "}", "{", "</", "=>", "->", "\t", " | ")
MIN_CJK_CHARS = 4

_SPAN_PATTERNS = (
    re.compile(r"\d[\d,.]*\s*(?:天|日|周|星期|个月|年|小时|分钟|秒|万|亿|%|个|次|人|件|条|项|台|页|MB|GB|KB|ms)"),
    re.compile(r"[「『《]([^」』》]{2,20})[」』》]"),
    re.compile(r"`([^`]{2,20})`"),
    re.compile(r"\b([A-Z][A-Z0-9_]{2,15})\b"),
)
_CLAUSE_SPLIT_RE = re.compile(r"[\n。；;！？!?]+")


def _digest(*parts: object) -> str:
    seed = "|".join(str(p) for p in parts)
    return hashlib.sha1(seed.encode("utf-8")).hexdigest()


def plain(text: object) -> str:
    """把卡面 HTML 变成可读纯文本；只做去标签与空白归一，不改字。"""
    value = str(text or "")
    value = re.sub(r"<br\s*/?>", "\n", value, flags=re.I)
    value = re.sub(r"</(?:p|div|li|tr)>", "\n", value, flags=re.I)
    # 两次解码 + 去标签：卡面里有双重转义的 HTML（&lt;b&gt;），只做一次会留下标签，
    # 而 plain() 又必须可重复调用（写入与校验各一次），所以这里做到收敛。
    for _ in range(2):
        value = html.unescape(value)
        value = re.sub(r"<[^>]+>", "", value)
    value = re.sub(r"[ \t\r\f\v]+", " ", value)
    value = re.sub(r" *\n *", "\n", value)
    return value.strip()


def normalize(text: object) -> str:
    return re.sub(r"\s+", " ", plain(text)).strip()


def clauses(text: object) -> list[str]:
    out = []
    for part in _CLAUSE_SPLIT_RE.split(plain(text)):
        item = part.strip().lstrip("-•· ").strip()
        item = item.rstrip("：:，,、").strip()
        if len(item) >= 4:
            out.append(item)
    return out


def span_candidates(text: str) -> list[tuple[int, int, str]]:
    """答案里可挖的片段：数字+单位、引号专名、反引号、全大写标识符。"""
    found: list[tuple[int, int, str]] = []
    seen: set[str] = set()
    for pattern in _SPAN_PATTERNS:
        for match in pattern.finditer(text):
            span = match.group(0) if match.lastindex is None else match.group(1)
            if not (MIN_CLOZE_SPAN <= len(span) <= MAX_CLOZE_SPAN):
                continue
            if span in seen or text.count(span) != 1:
                continue
            seen.add(span)
            found.append((match.start(), match.end(), span))
    return found


def _looks_like_code(text: str) -> bool:
    """代码块、模板占位、Markdown 表格压平后的一行——这些不是可背的句子。"""
    return any(marker in text for marker in CODE_MARKERS)


def _cjk_count(text: str) -> int:
    return len(re.findall(r"[\u4e00-\u9fff]", text))


def _span_ok(text: str, span: str) -> bool:
    """挖空/正确项不能切在 token 中间：30-40%、NetworkType.CONNECTED 都算。"""
    if _looks_like_code(span):
        return False
    if text.count(span) != 1:
        return False
    start = text.find(span)
    end = start + len(span)
    before = text[start - 1] if start else ""
    after = text[end] if end < len(text) else ""
    if before and before in "-.:：(" and False:
        return False
    if before in ("-", ".", ":"):
        return False
    if after in ("-", "%"):
        return False
    if before and before.isascii() and before.isalnum():
        return False
    if after and after.isascii() and after.isalnum():
        return False
    return True


def _window_around(text: str, span: str, limit: int) -> str | None:
    """把片段前后截到 limit 字以内：仍是原文子串，只是选了窗口，不是改写。"""
    index = text.find(span)
    if index < 0 or text.count(span) != 1 or len(span) >= limit:
        return None
    pad = (limit - len(span)) // 2
    start = max(0, index - pad)
    end = min(len(text), index + len(span) + pad)
    return text[start:end].strip()


def pick_excerpt(answer: str, max_chars: int, *, need_span: bool = False) -> str | None:
    """从答案里选一段逐字片段：优先带数字/专名的短句，其次短句本身。"""
    whole = normalize(answer)
    if not whole:
        return None
    if len(whole) <= max_chars and not need_span:
        return whole if not _looks_like_code(whole) and _cjk_count(whole) >= MIN_CJK_CHARS else None
    best: tuple[int, int, str] | None = None
    for index, item in enumerate(clauses(answer)):
        if not (MIN_OPTION_CHARS <= len(item) <= max_chars):
            continue
        if _looks_like_code(item) or _cjk_count(item) < MIN_CJK_CHARS:
            continue
        has_span = bool(span_candidates(item))
        if need_span and not has_span:
            continue
        score = (1 if has_span else 0, -abs(len(item) - max_chars // 2), -index)
        if best is None or score > best[0]:
            best = (score, index, item)  # type: ignore[assignment]
    return best[2] if best else None


def source_key(section: str, deck_name: str, card: dict) -> str:
    key = card.get("key")
    if isinstance(key, str) and key:
        return key
    full_name = f"{deck_name}::{section}" if section else deck_name
    return hashlib.sha1(identity_seed(full_name, card).encode("utf-8")).hexdigest()[:12]


@dataclass
class SourceCard:
    key: str
    section: str
    deck: str
    card: dict

    @property
    def q(self) -> str:
        return normalize(self.card.get("q", ""))

    @property
    def answer(self) -> str:
        return normalize(self.card.get("a", ""))

    @property
    def kind(self) -> str:
        kind = self.card.get("kind")
        if isinstance(kind, str) and kind:
            return kind
        for tag in self.card.get("tags") or []:
            if isinstance(tag, str) and tag.startswith("kind:"):
                return tag[5:]
        return ""

    @property
    def is_qa(self) -> bool:
        return self.card.get("type", "qa") == "qa"


def source_index(spec: DeckSpec) -> dict[str, SourceCard]:
    index: dict[str, SourceCard] = {}
    for section in spec.sections:
        name = section["deck"]
        full = f"{spec.name}::{name}" if name else spec.name
        for card in section["cards"]:
            key = source_key(name, spec.name, card)
            index.setdefault(key, SourceCard(key, name, full, card))
    return index


@dataclass
class DeriveOptions:
    options: int = 4
    max_option_chars: int = MAX_OPTION_CHARS
    cloze_max_span: int = MAX_CLOZE_SPAN
    cloze_per_card: int = 1
    choice_kinds: tuple[str, ...] = CHOICE_KINDS
    distractor_source: str = "hybrid"
    max_model_distractors: int = 2
    seed: int = 0
    sections: tuple[str, ...] = ()
    cloze_limit: int = 0
    choice_limit: int = 0
    show_source: str = "short"

    def check(self) -> None:
        if not (3 <= self.options <= 5):
            raise CardError("--options 必须在 3–5 之间")
        if not (MIN_OPTION_CHARS <= self.max_option_chars <= 200):
            raise CardError("--max-option-chars 必须在 2–200 之间")
        if not (MIN_CLOZE_SPAN <= self.cloze_max_span <= 60):
            raise CardError("--cloze-max-span 必须在 2–60 之间")
        if self.cloze_per_card not in (1, 2):
            raise CardError("--cloze-per-card 只能是 1 或 2")
        if self.distractor_source not in DISTRACTOR_SOURCES:
            raise CardError(f"--distractor-source 必须是 {'/'.join(DISTRACTOR_SOURCES)}")
        if self.show_source not in SOURCE_MODES:
            raise CardError(f"--show-source 必须是 {'/'.join(SOURCE_MODES)}")


def _too_similar(left: str, right: str) -> bool:
    from difflib import SequenceMatcher

    a, b = normalize(left), normalize(right)
    if not a or not b:
        return True
    if a == b or a in b or b in a:
        return True
    return SequenceMatcher(None, a, b).ratio() >= OPTION_SIMILARITY


def _option_ok(text: str, correct: str, stem: str, chosen: list[str]) -> bool:
    value = normalize(text)
    if not (MIN_OPTION_CHARS <= len(value) <= MAX_OPTION_CHARS):
        return False
    if any(banned in value for banned in BANNED_OPTIONS):
        return False
    ratio = len(value) / max(1, len(correct))
    if not (MIN_LENGTH_RATIO <= ratio <= MAX_LENGTH_RATIO):
        return False
    from difflib import SequenceMatcher

    if SequenceMatcher(None, value, stem).ratio() >= PHRASE_SIMILARITY:
        return False
    return not any(_too_similar(value, other) for other in [correct, *chosen])


def _local_pool(ingest: IngestData | None, max_chars: int) -> list[tuple[str, str]]:
    if ingest is None:
        return []
    pool: list[tuple[str, str]] = []
    for locator, text in ingest.locators.items():
        if "-" in locator:
            continue
        for item in clauses(text):
            if MIN_OPTION_CHARS <= len(item) <= max_chars:
                pool.append((locator, item))
        if len(pool) >= 4000:
            break
    return pool


def _cloze_entries(source: SourceCard, opts: DeriveOptions) -> tuple[list[dict], str | None]:
    if not source.is_qa:
        return [], "image_card"
    answer = source.answer
    if len(answer) < MIN_ANSWER_CHARS:
        return [], "answer_too_short"
    spans = span_candidates(answer)
    if not spans:
        return [], "no_cloze_span"
    entries: list[dict] = []
    for _, _, span in spans[: opts.cloze_per_card]:
        excerpt = pick_excerpt(answer, MAX_CLOZE_TEXT)
        if excerpt is None or span not in excerpt:
            for item in clauses(answer):
                if span in item and len(item) <= MAX_CLOZE_TEXT:
                    excerpt = item
                    break
        if excerpt is None or span not in excerpt:
            excerpt = _window_around(answer, span, MAX_CLOZE_TEXT)
        if excerpt is None or span not in excerpt or len(span) > opts.cloze_max_span:
            continue
        if _looks_like_code(excerpt) or _looks_like_code(span):
            continue
        if _cjk_count(excerpt) < MIN_CJK_CHARS or not _span_ok(excerpt, span):
            continue
        if excerpt.count(span) != 1:
            continue
        text = excerpt.replace(span, "{{c1::" + span + "}}")
        entries.append({
            "type": "cloze",
            "source_key": source.key,
            "source_q": source.q,
            "kind": source.kind,
            "source_excerpt": excerpt,
            "text": text,
            "extra": f"原题：{source.q}",
            "span_origin": "rule",
        })
    return entries, None if entries else "code_snippet"


def _choice_entry(source: SourceCard, index: dict[str, SourceCard],
                  local_pool: list[tuple[str, str]], opts: DeriveOptions) -> tuple[dict | None, str | None]:
    if not source.is_qa:
        return None, "image_card"
    if source.kind and source.kind not in opts.choice_kinds:
        return None, None
    answer = source.answer
    if len(answer) < MIN_ANSWER_CHARS:
        return None, "answer_too_short"
    correct = pick_excerpt(answer, opts.max_option_chars)
    if correct is None:
        return None, "code_snippet"
    if _looks_like_code(correct) or _cjk_count(correct) < MIN_CJK_CHARS:
        return None, "code_snippet"
    stem = source.q
    distractors: list[dict] = []
    seen = {normalize(correct)}

    def accept(text: str) -> bool:
        value = normalize(text)
        if value in seen:
            return False
        if not _option_ok(value, correct, stem, [d["text"] for d in distractors]):
            return False
        seen.add(value)
        return True

    tiers = {
        "same-deck": ("same-deck",),
        "local": ("same-deck", "local"),
        "hybrid": ("same-deck", "local", "model"),
        "none": (),
    }[opts.distractor_source]

    if "same-deck" in tiers:
        pool = [s for s in index.values() if s.key != source.key]
        pool.sort(key=lambda s: (s.section != source.section,
                                 s.kind != source.kind,
                                 abs(len(s.answer) - len(correct)),
                                 s.key))
        for other in pool:
            if len(distractors) >= opts.options - 1:
                break
            candidate = pick_excerpt(other.answer, opts.max_option_chars)
            if candidate and accept(candidate):
                distractors.append({"text": normalize(candidate), "correct": False,
                                    "origin": "same-deck", "source_key": other.key})
    if "local" in tiers and len(distractors) < opts.options - 1:
        for locator, item in local_pool:
            if len(distractors) >= opts.options - 1:
                break
            if accept(item):
                distractors.append({"text": normalize(item), "correct": False,
                                    "origin": "local", "source": locator})
    if len(distractors) < opts.options - 1:
        return None, "not_enough_distractors"

    options = [{"text": correct, "correct": True}] + distractors
    order = sorted(range(len(options)),
                   key=lambda i: _digest(opts.seed, source.key, i))
    shuffled = [options[i] for i in order]
    answer_index = next(i for i, item in enumerate(shuffled) if item.get("correct"))
    for item in shuffled:
        item.pop("correct", None)
    return {
        "type": "choice",
        "source_key": source.key,
        "source_q": source.q,
        "kind": source.kind,
        "stem": stem,
        "source_excerpt": correct,
        "options": shuffled,
        "answer_index": answer_index,
        "explanation": "",
    }, None


def build_plan(spec: DeckSpec, ingest: IngestData | None,
               opts: DeriveOptions) -> dict:
    opts.check()
    index = source_index(spec)
    local_pool = _local_pool(ingest, opts.max_option_chars)
    cards: list[dict] = []
    skipped: list[dict] = []
    stats = {"cloze": 0, "choice": 0,
             "skipped": {}, "sources": len(index)}
    for source in index.values():
        if opts.sections and source.section not in opts.sections:
            continue
        cloze, reason = _cloze_entries(source, opts)
        if cloze:
            cards.extend(cloze)
            stats["cloze"] += len(cloze)
        elif reason:
            skipped.append({"source_key": source.key, "reason": reason})
        choice, reason = _choice_entry(source, index, local_pool, opts)
        if choice:
            cards.append(choice)
            stats["choice"] += 1
        elif reason:
            skipped.append({"source_key": source.key, "reason": reason})
    if opts.cloze_limit:
        kept = 0
        trimmed: list[dict] = []
        for card in cards:
            if card["type"] == "cloze":
                if kept >= opts.cloze_limit:
                    continue
                kept += 1
            trimmed.append(card)
        cards = trimmed
    if opts.choice_limit:
        kept = 0
        trimmed = []
        for card in cards:
            if card["type"] == "choice":
                if kept >= opts.choice_limit:
                    continue
                kept += 1
            trimmed.append(card)
        cards = trimmed
    seen_bodies: set[str] = set()
    unique: list[dict] = []
    for card in cards:
        if card["type"] == "cloze":
            body = "cloze|" + re.sub(r"\{\{c1::(.+?)\}\}", r"\1", str(card.get("text", "")))
        else:
            body = "choice|" + str(card.get("stem", "")) + "|" + "|".join(
                normalize(item.get("text", "")) for item in card.get("options") or [])
        body = normalize(body)
        if body in seen_bodies:
            skipped.append({"source_key": card["source_key"], "reason": "duplicate"})
            continue
        seen_bodies.add(body)
        unique.append(card)
    cards = unique
    stats["duplicate"] = len(seen_bodies)
    for item in skipped:
        stats["skipped"][item["reason"]] = stats["skipped"].get(item["reason"], 0) + 1
    return {
        "version": DERIVED_VERSION,
        "source": {"deck": spec.name, "cards": len(index)},
        "options": {
            "count": opts.options,
            "max_option_chars": opts.max_option_chars,
            "distractor_source": opts.distractor_source,
            "seed": opts.seed,
            "show_source": opts.show_source,
        },
        "cards": cards,
        "skipped": skipped,
    }


def _load_plan_dict(plan: dict) -> dict:
    if not isinstance(plan, dict):
        raise CardError("派生 plan 必须是对象")
    if plan.get("version") != DERIVED_VERSION:
        raise CardError(f"派生 plan 的 version 必须是 {DERIVED_VERSION}")
    if not isinstance(plan.get("cards"), list):
        raise CardError("派生 plan 缺少 cards 数组")
    return plan


def load_derived_plan(path: str | Path) -> dict:
    import json

    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise CardError(f"找不到派生 plan: {path}") from exc
    except json.JSONDecodeError as exc:
        raise CardError(f"派生 plan 不是合法 JSON: {path}（{exc}）") from exc
    return _load_plan_dict(data)


def derive_key(deck_name: str, section: str, source: str, seq: int) -> str:
    return _digest("derive", deck_name, section, source, seq)[:12]


def _options_of(entry: dict) -> list[str]:
    return [normalize(item.get("text", "")) for item in entry.get("options") or []]


def _render_choice(entry: dict) -> tuple[str, str]:
    letters = "ABCDE"
    options = entry.get("options") or []
    lines = [f"{letters[i]}. {normalize(item.get('text', ''))}" for i, item in enumerate(options)]
    q = entry["stem"] + "\n\n" + "\n".join(lines)
    index = int(entry.get("answer_index") or 0)
    a = f"{letters[index]}. {normalize(options[index].get('text', ''))}"
    if entry.get("explanation"):
        a += "\n\n" + str(entry["explanation"]).strip()
    return q, a


def _source_line(entry: dict, mode: str) -> str:
    question = normalize(entry.get("source_q", ""))
    if mode == "off" or not question:
        return ""
    if mode == "full":
        return f"來源：{question}"
    return f"來源：{question[:80]}"


def check_plan(plan: dict, spec: DeckSpec, ingest: IngestData | None = None,
               allow_model: bool = False) -> tuple[Report, dict]:
    report = Report()
    stats = {"cloze": 0, "choice": 0, "model_options": 0,
             "origins": {}, "answer_positions": {}}
    index = source_index(spec)
    seen_pairs: set[tuple[str, str]] = set()
    seen_bodies: dict[str, str] = {}
    for i, entry in enumerate(plan.get("cards") or []):
        where = f"cards[{i}]"
        if not isinstance(entry, dict):
            report.add_error(where, "必须是对象")
            continue
        ctype = entry.get("type")
        if ctype not in ("cloze", "choice"):
            report.add_error(f"{where}.type", f"必须是 cloze/choice，实际为 {ctype!r}")
            continue
        source = index.get(str(entry.get("source_key") or ""))
        if source is None:
            report.add_error(f"{where}.source_key", "源卡不存在")
            continue
        if not source.is_qa:
            report.add_error(f"{where}.source_key", "源卡不是 qa（image/cloze 不能派生）")
        if normalize(entry.get("source_q", "")) != source.q:
            report.add_error(f"{where}.source_q", "与源卡问题不一致（源卡可能改过）")
        pair = (entry["source_key"], ctype)
        if pair in seen_pairs:
            report.add_error(f"{where}", "同一源卡 + 同一类型的派生卡重复")
        seen_pairs.add(pair)
        if ctype == "cloze":
            text = str(entry.get("text") or "")
            markers = re.findall(r"\{\{c1::(.+?)\}\}", text)
            if not markers:
                report.add_error(f"{where}.text", "cloze 卡缺少 {{c1::…}}")
                continue
            excerpt = normalize(entry.get("source_excerpt", ""))
            if not excerpt:
                report.add_error(f"{where}.source_excerpt", "缺少逐字片段")
                continue
            if excerpt not in source.answer:
                report.add_error(f"{where}.source_excerpt", "片段不是源答案的逐字子串")
            for span in markers:
                if len(span) > MAX_CLOZE_SPAN:
                    report.add_error(f"{where}.text", f"挖空片段超过 {MAX_CLOZE_SPAN} 字")
                if excerpt.count(span) != 1:
                    report.add_error(f"{where}.text", "挖空片段在片段里不唯一")
            stripped = re.sub(r"\{\{c1::(.+?)\}\}", r"\1", text)
            if normalize(stripped) != excerpt:
                report.add_error(f"{where}.text", "填空文本与逐字片段不一致（疑似改写）")
            body = "cloze|" + normalize(stripped)
            stats["cloze"] += 1
        else:
            stem = normalize(entry.get("stem", ""))
            if not stem:
                report.add_error(f"{where}.stem", "选择题缺少题干")
            options = _options_of(entry)
            count = len(options)
            if not (3 <= count <= 5):
                report.add_error(f"{where}.options", f"选项数 {count} 不在 3–5")
            try:
                answer_index = int(entry.get("answer_index"))
            except (TypeError, ValueError):
                report.add_error(f"{where}.answer_index", "必须是整数")
                continue
            if not (0 <= answer_index < count):
                report.add_error(f"{where}.answer_index", "越界")
                continue
            correct = source.answer
            excerpt = normalize(entry.get("source_excerpt", ""))
            if normalize(options[answer_index]) != excerpt:
                report.add_error(f"{where}.answer_index", "正确项与 source_excerpt 不一致")
            if excerpt not in correct:
                report.add_error(f"{where}.source_excerpt", "正确项不是源答案的逐字子串")
            if len(excerpt) > MAX_OPTION_CHARS:
                report.add_error(f"{where}.source_excerpt", f"正确项超过 {MAX_OPTION_CHARS} 字")
            for j, option in enumerate(options):
                if not (MIN_OPTION_CHARS <= len(option) <= MAX_OPTION_CHARS):
                    report.add_error(f"{where}.options[{j}]", "选项长度越界")
                for k in range(j + 1, count):
                    if _too_similar(option, options[k]):
                        report.add_error(f"{where}.options", f"选项 {j} 与 {k} 太像或重复")
            raw_options = entry.get("options") or []
            for j, item in enumerate(raw_options):
                origin = item.get("origin")
                if j == answer_index:
                    continue
                if origin == "same-deck":
                    if item.get("source_key") not in index:
                        report.add_error(f"{where}.options[{j}]", "same-deck 干扰项的 source_key 不存在")
                elif origin == "local":
                    locator = str(item.get("source") or "")
                    if not locator:
                        report.add_error(f"{where}.options[{j}]", "local 干扰项缺少 source 定位")
                    elif ingest is not None and locator in ingest.locators:
                        if options[j] not in normalize(ingest.locators[locator]):
                            report.add_error(f"{where}.options[{j}]", "local 干扰项在该定位文本里找不到")
                elif origin == "model":
                    stats["model_options"] += 1
                else:
                    report.add_error(f"{where}.options[{j}]", "origin 必须是 same-deck/local/model")
                stats["origins"][str(origin)] = stats["origins"].get(str(origin), 0) + 1
            if stats["model_options"] and not allow_model:
                report.add_warning(where, "含模型干扰项：编译需 --allow-model-distractors")
            body = "choice|" + stem + "|" + "|".join(options)
            stats["answer_positions"][str(answer_index)] = stats["answer_positions"].get(str(answer_index), 0) + 1
            stats["choice"] += 1
        if body in seen_bodies:
            report.add_error(where, f"与 {seen_bodies[body]} 渲染内容相同")
        else:
            seen_bodies[body] = where
    for i, entry in enumerate(plan.get("skipped") or []):
        where = f"skipped[{i}]"
        if not isinstance(entry, dict) or entry.get("source_key") not in index:
            report.add_error(where, "source_key 不存在")
            continue
        if entry.get("reason") not in SKIP_REASONS:
            report.add_error(f"{where}.reason", f"必须是 {'/'.join(SKIP_REASONS)} 之一")
    return report, stats


def build_deck(plan: dict, spec: DeckSpec) -> DeckData:
    deck = DeckData(name=spec.name, source_kind=spec.source_kind)
    show = str((plan.get("options") or {}).get("show_source") or "short")
    seq: dict[tuple[str, str], int] = {}
    for entry in plan.get("cards") or []:
        ctype = entry["type"]
        section = "填空" if ctype == "cloze" else "选择题"
        pair = (entry["source_key"], ctype)
        number = seq.get(pair, 0)
        seq[pair] = number + 1
        key = derive_key(spec.name, section, entry["source_key"], number)
        tags = [f"derived:{ctype}", f"derived-from:{entry['source_key']}"]
        if entry.get("kind"):
            tags.append(f"kind:{entry['kind']}")
        # 选择题不新增笔记类型：渲染进 qa（正面题干+选项，背面答案+來源）。
        card: dict = {"type": "cloze" if ctype == "cloze" else "qa",
                      "source": f"derived:{entry['source_key']}",
                      "tags": tags, "key": key}
        if ctype == "cloze":
            card["text"] = entry["text"]
            card["extra"] = entry.get("extra") or f"原题：{entry.get('source_q', '')}"
        else:
            q, a = _render_choice(entry)
            line = _source_line(entry, show)
            if line:
                a = f"{a}\n\n{line}"
            card["q"] = q
            card["a"] = a
        deck.add(section, card)
    return deck


def compile_plan(plan: dict, spec: DeckSpec, out: str | Path,
                 allow_model: bool = False, force: bool = False) -> Path:
    report, _ = check_plan(plan, spec, allow_model=allow_model)
    if not report.ok:
        raise CardError("派生 plan 有错误，拒绝编译：" + "；".join(report.errors[:3]))
    deck = build_deck(plan, spec)
    return write_deck(deck, out, force=force)


PACKET_INSTRUCTIONS = (
    "这是给外部模型（或人）的派生题素材包，不是计划文件。"
    "请只做三件事：①从每个 answer 里挑出可以挖空的逐字片段（数字+单位、专名、术语，2–20 字）；"
    "②为 fact/procedure 卡的建议题干写 3–4 个干扰项候选；"
    "③标出哪些卡不值得出题。"
    "所有片段与干扰项都必须是对应 answer 的逐字子串，不许改写、摘要或编造；"
    "输出按 plan_derive.json 的 cards/skipped 结构，交回 derive check 校验。"
)


def build_packet(spec: DeckSpec, limit: int = 0,
                 sections: tuple[str, ...] = ()) -> dict:
    """只读导出源卡文本，供外部模型挑选挖空与干扰项；工具本身不调用模型。"""
    index = source_index(spec)
    cards: list[dict] = []
    for source in index.values():
        if sections and source.section not in sections:
            continue
        if not source.is_qa or len(source.answer) < MIN_ANSWER_CHARS:
            continue
        cards.append({
            "source_key": source.key,
            "section": source.section,
            "kind": source.kind,
            "q": source.q,
            "answer": source.answer,
            "source": source.card.get("source", ""),
        })
        if limit and len(cards) >= limit:
            break
    return {
        "version": 1,
        "deck": spec.name,
        "instructions": PACKET_INSTRUCTIONS,
        "count": len(cards),
        "cards": cards,
    }


def summary(plan: dict) -> str:
    cards = plan.get("cards") or []
    cloze = sum(1 for c in cards if c.get("type") == "cloze")
    choice = len(cards) - cloze
    origins: dict[str, int] = {}
    for card in cards:
        for item in card.get("options") or []:
            origin = item.get("origin")
            if not origin:
                continue  # 正确项没有 origin，它不是"干扰项"
            origins[origin] = origins.get(origin, 0) + 1
    skipped: dict[str, int] = {}
    for item in plan.get("skipped") or []:
        skipped[item.get("reason", "?")] = skipped.get(item.get("reason", "?"), 0) + 1
    tail = " / ".join(f"{k} {v}" for k, v in sorted(skipped.items())) or "无"
    origin_text = " / ".join(f"{k} {v}" for k, v in sorted(origins.items())) or "无"
    return (f"填空 {cloze} / 选择 {choice}；干扰项 {origin_text}；"
            f"未出卡 {len(plan.get('skipped') or [])}（{tail}）")
