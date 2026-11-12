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
import json
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
    "derived_card",
    "exam_source",
    "option_length_ratio",
)

CANDIDATES_VERSION = 1
MAX_MODEL_PER_CARD = 2
SEMANTIC_ORIGIN = "semantic"
SEED_MIN_SCORE = 0.68
OPTION_LENGTH_RATIO_MAX = 2.0
CANDIDATES_FORMAT = {"items": [{"source_key": "源卡 key", "distractors": ["候选干扰项"]}]}

CHOICE_KINDS = ("fact", "procedure")
DISTRACTOR_SOURCES = ("same-deck", "local", "hybrid", "none")
SOURCE_MODES = ("short", "full", "off")
MAX_CONTRAST_SOURCES = 3
CONTRAST_MIN_QUOTE = 8
CONTRAST_MAX_QUOTE = 300

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


_DANGLING_TAIL = re.compile(r"(?:例如|比如|包括|分为|如下|即|如)$")
_EXAM_OPTION = re.compile(r"<br\s*/?>\s*[A-E][.、]")
_EXAM_ANSWER = re.compile(r"正确答案[：:]")


def _is_exam_source(source: SourceCard) -> bool:
    """题库导出格式的卡：选项嵌在题干里，答案带「正确答案：」。"""
    return bool(_EXAM_OPTION.search(source.card.get("q", "") or "")
                or _EXAM_ANSWER.search(source.card.get("a", "") or ""))


def _too_similar(left: str, right: str) -> bool:
    from difflib import SequenceMatcher

    a, b = normalize(left), normalize(right)
    if not a or not b:
        return True
    if a == b or a in b or b in a:
        return True
    return SequenceMatcher(None, a, b).ratio() >= OPTION_SIMILARITY


_BAD_HEAD = "`*+-.,;:!?、。，；：）)]】」』’”“\"' "
_BAD_TAIL = "，、；：,;:（([【「『‘“\"' "


def _option_shape_ok(text: str) -> bool:
    value = text.strip()
    if not value:
        return False
    if value[0] in _BAD_HEAD or value[-1] in _BAD_TAIL:
        return False
    return True


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
        span = span.strip()
        if "`" in span or _DANGLING_TAIL.search(span):
            continue
        if normalize(span) in normalize(source.deck):
            # 「MQTT」「Android」这类牌组主题词，挖空等于白送。
            continue
        if normalize(span) in source.q:
            # 挖空词已经在问题里出现过，等于把答案印在正面。
            continue
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
                  local_pool: list[tuple[str, str]], opts: DeriveOptions,
                  semantic: list[str] | None = None) -> tuple[dict | None, str | None]:
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
        if not _option_shape_ok(value):
            return False
        if len(value) / max(1, len(correct)) > OPTION_LENGTH_RATIO_MAX:
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
        # 先按「同 section、同 kind」圈定候选，再按摘录长度与正确项的差排序：
        # 长度接近的干扰项不会靠长短被一眼排除，也不容易把正确项衬得突兀。
        pool = [s for s in index.values() if s.key != source.key]
        cache: dict[str, str | None] = {}

        def excerpt_of(other: SourceCard) -> str | None:
            if other.key not in cache:
                cache[other.key] = pick_excerpt(other.answer, opts.max_option_chars)
            return cache[other.key]

        from difflib import SequenceMatcher

        def topic(a: str, b: str) -> float:
            return SequenceMatcher(None, a[:80], b[:80]).ratio()

        ranked: list[tuple[int, int, float, int, str, SourceCard, str]] = []
        for other in pool:
            candidate = excerpt_of(other)
            if not candidate:
                continue
            related = max(topic(other.q, stem), topic(candidate, correct))
            ranked.append((int(other.section != source.section),
                           int(other.kind != source.kind),
                           related,
                           abs(len(candidate) - len(correct)),
                           other.key, other, candidate))
        # 长度带内优先贴题：先限 0.7–1.5，不够再放 0.5–2.0，最后才退回全池。
        # 只按长度排会选出无关选项，只按主题排又会把长短差拉大。
        def ordered(lo: float, hi: float):
            band = [item for item in ranked
                    if lo <= len(item[6]) / max(1, len(correct)) <= hi]
            band.sort(key=lambda item: (-item[2], item[0], item[1], item[3], item[4]))
            return band

        ranked.sort(key=lambda item: (-item[2], item[0], item[1], item[3], item[4]))
        shortlist = (ordered(0.7, 1.5) or ordered(0.5, 2.0)
                     or [item for item in ranked
                         if len(item[6]) / max(1, len(correct)) <= 2.0]
                     or ranked)
        for _, _, _, _, _, other, candidate in shortlist:
            if len(distractors) >= opts.options - 1:
                break
            if accept(candidate):
                distractors.append({"text": normalize(candidate), "correct": False,
                                    "origin": "same-deck", "source_key": other.key})
    if semantic:
        for item in semantic:
            if len(distractors) >= opts.options - 1:
                break
            if accept(item):
                distractors.append({"text": normalize(item), "correct": False,
                                    "origin": SEMANTIC_ORIGIN})
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

    def ratio_ok(items: list[dict]) -> bool:
        lens = [len(item["text"]) for item in items]
        return max(lens) / max(1, min(lens)) <= OPTION_LENGTH_RATIO_MAX

    while not ratio_ok(options) and len(options) > 3:
        victims = [i for i, item in enumerate(options) if not item.get("correct")]
        shortest = min(victims, key=lambda i: len(options[i]["text"]))
        options.pop(shortest)
    if not ratio_ok(options):
        return None, "option_length_ratio"

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


def load_seeds(path) -> dict:
    """读 semantic_map.py 产出的关系表；结构不对直接拒绝，不做猜测。"""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("version") != 1 or not isinstance(data.get("cards"), dict):
        raise CardError(f"{path} 不是 semantic_map.py 产出的 seeds.json（需要 version=1 与 cards 对象）")
    return data


def _seed_pool(seeds: dict | None, key: str, max_chars: int) -> list[str]:
    """取该卡语义邻居的答案开头，作为干扰项候选；只做池，不保证可用。"""
    if not seeds:
        return []
    cards = seeds.get("cards") or {}
    entry = cards.get(key) or {}
    cluster = entry.get("cluster")
    out: list[str] = []
    for item in entry.get("neighbors") or []:
        try:
            score = float(item.get("score") or 0.0)
        except (TypeError, ValueError):
            score = 0.0
        if score < SEED_MIN_SCORE:
            continue
        other = cards.get(item.get("key")) or {}
        if cluster and other.get("cluster") and other["cluster"] != cluster:
            continue
        raw = str(other.get("answer") or other.get("answer_head") or "")
        excerpt = pick_excerpt(plain(raw), max_chars)
        text = normalize(excerpt or "")
        if len(text) < MIN_OPTION_CHARS or text in out:
            continue
        out.append(text)
    return out


def _worst_same_deck(options: list[dict], answer_index: int, correct: str) -> int | None:
    best, victim = -1, None
    for k, opt in enumerate(options):
        if k == answer_index or not isinstance(opt, dict) or opt.get("origin") != "same-deck":
            continue
        gap = abs(len(normalize(str(opt.get("text", "")))) - len(correct))
        if gap > best:
            best, victim = gap, k
    return victim


def build_plan(spec: DeckSpec, ingest: IngestData | None,
               opts: DeriveOptions, seeds: dict | None = None) -> dict:
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
        if _is_exam_source(source):
            # 题库导出格式：q 里内嵌 <br>A./B. 选项、a 以「正确答案：X.」开头。
            # 同一知识点通常已有一张干净卡，派生只认干净卡。
            skipped.append({"source_key": source.key, "reason": "exam_source"})
            continue
        tags = [t for t in (source.card.get("tags") or []) if isinstance(t, str)]
        if any(t.startswith("derived:") for t in tags):
            # 派生题不再二次派生：否则会从对比题里再出一道「选择/填空」。
            skipped.append({"source_key": source.key, "reason": "derived_card"})
            continue
        cloze, reason = _cloze_entries(source, opts)
        if cloze:
            cards.extend(cloze)
            stats["cloze"] += len(cloze)
        elif reason:
            skipped.append({"source_key": source.key, "reason": reason})
        semantic = _seed_pool(seeds, source.key, opts.max_option_chars)
        choice, reason = _choice_entry(source, index, local_pool, opts, semantic)
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



def load_candidates(path: str | Path) -> list[dict]:
    """读取外部模型写的干扰项候选；坏结构直接拒绝，不做猜测。"""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CardError(f"读不了候选文件 {path}：{exc}") from exc
    if isinstance(data, dict):
        items = data.get("items") or data.get("candidates") or []
    elif isinstance(data, list):
        items = data
    else:
        raise CardError(f"{path} 必须是对象或数组")
    if not isinstance(items, list):
        raise CardError(f"{path} 的 items 必须是数组")
    out: list[dict] = []
    for i, item in enumerate(items):
        if not isinstance(item, dict):
            raise CardError(f"candidates[{i}] 必须是对象")
        key = str(item.get("source_key") or "").strip()
        if not key:
            raise CardError(f"candidates[{i}].source_key 不能为空")
        raw = item.get("distractors")
        if not isinstance(raw, list):
            raise CardError(f"candidates[{i}].distractors 必须是数组")
        out.append({"source_key": key,
                    "distractors": [str(d) for d in raw if str(d).strip()]})
    return out


def _bump(counter: dict[str, int], key: str) -> None:
    counter[key] = counter.get(key, 0) + 1


def merge_candidates(plan: dict, candidates: list[dict],
                     max_per_card: int = MAX_MODEL_PER_CARD,
                     replace_same_deck: bool = False,
                     prefer_model: bool = False,
                     seeds: dict | None = None,
                     prefer_semantic: bool = False) -> tuple[list[str], dict]:
    """把模型候选并进对应选择题：长度、重复、相似度都过闸，超上限就拒绝。

    只标记 `review: true`，不替人拍板；真正的拦截在 check_plan 的 model 规则与
    compile 的 --allow-model-distractors。
    """
    by_key: dict[str, list[dict]] = {}
    for card in plan.get("cards") or []:
        if card.get("type") == "choice":
            by_key.setdefault(str(card.get("source_key") or ""), []).append(card)

    warnings: list[str] = []
    stats = {"cards": 0, "added": 0, "replaced": 0, "rejected": {}}
    for item in candidates:
        cards = by_key.get(item["source_key"]) or []
        if not cards:
            warnings.append(f"{item['source_key']}：plan 里没有对应的选择题，候选被忽略")
            continue
        card = cards[0]
        options = card.setdefault("options", [])
        answer_index = int(card.get("answer_index", -1))
        correct = normalize(card.get("source_excerpt", ""))
        existing = {normalize(str(o.get("text", ""))) for o in options}
        model_count = sum(1 for o in options if o.get("origin") == "model")
        added_here = 0

        def worst_same_deck() -> int | None:
            best, victim = -1, None
            for k, opt in enumerate(options):
                if k == answer_index or opt.get("origin") != "same-deck":
                    continue
                gap = abs(len(normalize(str(opt.get("text", "")))) - len(correct))
                if gap > best:
                    best, victim = gap, k
            return victim

        for raw in item["distractors"]:
            text = normalize(raw)
            if not text:
                continue
            if not (MIN_OPTION_CHARS <= len(text) <= MAX_OPTION_CHARS):
                _bump(stats["rejected"], "长度越界")
                continue
            if model_count >= max_per_card:
                _bump(stats["rejected"], "超过每题模型候选上限")
                break
            if prefer_model:
                victim = worst_same_deck()
                if victim is not None:
                    options[victim] = {"text": text, "origin": "model", "review": True}
                    existing.add(text)
                    model_count += 1
                    added_here += 1
                    stats["replaced"] += 1
                    continue
            if len(options) >= 5:
                victim = None
                if replace_same_deck:
                    best = -1
                    for k, item in enumerate(options):
                        if k == answer_index or item.get("origin") != "same-deck":
                            continue
                        gap = abs(len(normalize(str(item.get("text", "")))) - len(correct))
                        if gap > best:
                            best, victim = gap, k
                if victim is None:
                    _bump(stats["rejected"], "选项已满 5 个")
                    break
                options[victim] = {"text": text, "origin": "model", "review": True}
                existing.add(text)
                model_count += 1
                added_here += 1
                stats["replaced"] += 1
                continue
            if text in existing or _too_similar(text, correct):
                _bump(stats["rejected"], "与已有选项或正确项重复")
                continue
            if any(_too_similar(text, other) for other in existing if other):
                _bump(stats["rejected"], "与已有选项太像")
                continue
            options.append({"text": text, "origin": "model", "review": True})
            existing.add(text)
            model_count += 1
            added_here += 1
        if added_here:
            card["review"] = True
            stats["cards"] += 1
            stats["added"] += added_here
    semantic_added = semantic_replaced = 0
    per_card_limit = 99 if prefer_semantic else 1
    if seeds:
        for card in [c for c in plan.get("cards") or [] if c.get("type") == "choice"]:
            key = str(card.get("source_key") or "")
            pool = _seed_pool(seeds, key, MAX_OPTION_CHARS)
            options = card.get("options") or []
            if not pool or not options:
                continue
            answer_index = int(card.get("answer_index", -1))
            correct = normalize(card.get("source_excerpt", ""))
            existing = {normalize(str(o.get("text", ""))) for o in options}
            changed = 0
            for text in pool:
                if changed >= per_card_limit:
                    break
                if text in existing or _too_similar(text, correct):
                    continue
                if any(_too_similar(text, other) for other in existing if other):
                    continue
                victim = _worst_same_deck(options, answer_index, correct) if len(options) >= 3 else None
                if len(options) < 3:
                    options.append({"text": text, "origin": SEMANTIC_ORIGIN})
                    semantic_added += 1
                elif victim is not None:
                    options[victim] = {"text": text, "origin": SEMANTIC_ORIGIN}
                    semantic_replaced += 1
                else:
                    break
                existing.add(text)
                changed += 1
            if changed:
                card["review"] = True
    stats["semantic_added"] = semantic_added
    stats["semantic_replaced"] = semantic_replaced
    return warnings, stats

def _squeeze(text) -> str:
    """去掉全部空白：HTML 标签清理会在中文里留下空格，逐字比对时忽略它们。"""
    return re.sub(r"\s+", "", str(text or ""))


def _check_contrast(entry: dict, index: dict, where: str, report, stats) -> str | None:
    """对比题：sources 里每条引用都必须逐字来自源卡答案，答案必须包含它们。"""
    sources = entry.get("sources")
    if not isinstance(sources, list) or not (1 <= len(sources) <= MAX_CONTRAST_SOURCES):
        report.add_error(f"{where}.sources", f"必须是 1–{MAX_CONTRAST_SOURCES} 条 {{key, quote}}")
        return None
    quotes: list[str] = []
    for j, item in enumerate(sources):
        if not isinstance(item, dict):
            report.add_error(f"{where}.sources[{j}]", "必须是对象")
            continue
        src = index.get(str(item.get("key") or ""))
        if src is None:
            report.add_error(f"{where}.sources[{j}].key", "源卡不存在")
            continue
        quote = normalize(item.get("quote", ""))
        if not (CONTRAST_MIN_QUOTE <= len(quote) <= CONTRAST_MAX_QUOTE):
            report.add_error(f"{where}.sources[{j}].quote",
                             f"长度必须在 {CONTRAST_MIN_QUOTE}–{CONTRAST_MAX_QUOTE} 字，实际 {len(quote)}")
            continue
        if _squeeze(quote) not in _squeeze(src.answer):
            report.add_error(f"{where}.sources[{j}].quote", "不是源卡答案的逐字子串")
            continue
        quotes.append(quote)
    if len({_squeeze(q) for q in quotes}) != len(quotes):
        report.add_error(f"{where}.sources", "引用不能重复")
    q = normalize(entry.get("q", ""))
    if not q:
        report.add_error(f"{where}.q", "缺少问题")
    a = normalize(entry.get("a", ""))
    if not a:
        report.add_error(f"{where}.a", "缺少答案")
    squeezed_answer = _squeeze(a)
    for quote in quotes:
        if _squeeze(quote) not in squeezed_answer:
            report.add_error(f"{where}.a", "答案必须包含每条引用原文（逐字），不能只写结论")
            break
    stats["contrast"] = stats.get("contrast", 0) + 1
    return "contrast|" + q + "|" + "|".join(quotes)


def check_plan(plan: dict, spec: DeckSpec, ingest: IngestData | None = None,
               allow_model: bool = False) -> tuple[Report, dict]:
    report = Report()
    stats = {"cloze": 0, "choice": 0, "contrast": 0, "model_options": 0,
             "review": 0, "origins": {}, "answer_positions": {}}
    index = source_index(spec)
    seen_pairs: set[tuple[str, str]] = set()
    seen_bodies: dict[str, str] = {}
    for i, entry in enumerate(plan.get("cards") or []):
        where = f"cards[{i}]"
        if not isinstance(entry, dict):
            report.add_error(where, "必须是对象")
            continue
        ctype = entry.get("type")
        if ctype not in ("cloze", "choice", "contrast"):
            report.add_error(f"{where}.type", f"必须是 cloze/choice/contrast，实际为 {ctype!r}")
            continue
        if ctype == "contrast":
            body = _check_contrast(entry, index, where, report, stats)
            if body:
                if body in seen_bodies:
                    report.add_error(where, f"与 {seen_bodies[body]} 渲染内容相同")
                else:
                    seen_bodies[body] = where
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
                elif origin == SEMANTIC_ORIGIN:
                    stats["semantic_options"] = stats.get("semantic_options", 0) + 1
                else:
                    report.add_error(f"{where}.options[{j}]", "origin 必须是 same-deck/local/model/semantic")
                stats["origins"][str(origin)] = stats["origins"].get(str(origin), 0) + 1
            model_here = sum(1 for k, item in enumerate(raw_options)
                             if k != answer_index and isinstance(item, dict)
                             and item.get("origin") == "model")
            if model_here > MAX_MODEL_PER_CARD:
                report.add_error(f"{where}.options",
                                 f"模型干扰项 {model_here} 个，超过上限 {MAX_MODEL_PER_CARD}")
            lens = [len(normalize(str(o.get("text", "")))) for o in raw_options]
            if len(lens) >= 2 and min(lens) and max(lens) / min(lens) > OPTION_LENGTH_RATIO_MAX:
                report.add_warning(f"{where}.options",
                                   f"选项长度比 {max(lens) / min(lens):.1f}（最短 {min(lens)} / 最长 {max(lens)}）：长度可能泄漏答案")
            if entry.get("review"):
                report.add_warning(where, "含模型候选（review: true）：编译前需人工复审")
                stats["review"] += 1
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
    index = source_index(spec)
    seq: dict[tuple[str, str], int] = {}
    for entry in plan.get("cards") or []:
        ctype = entry["type"]
        if ctype == "contrast":
            keys = [str(item.get("key")) for item in entry.get("sources") or []]
            ordered = list(dict.fromkeys(keys))
            # 用「源卡串 + 题干」做基座：候选增删时，保留下来的对比题 key 不漂移。
            base = "|".join(ordered) + "|" + str(entry.get("q") or "")
            key = derive_key(spec.name, "对比题", base, 0)
            tags = ["derived:contrast", "derived-from:" + ",".join(ordered)]
            if entry.get("kind"):
                tags.append(f"kind:{entry['kind']}")
            answer = str(entry.get("a") or "")
            if show != "off":
                lines = []
                for one in ordered:
                    src = index.get(one)
                    if src:
                        lines.append(src.q if len(src.q) <= 80 else src.q[:80] + "…")
                if lines:
                    answer = f"{answer}\n\n來源：" + " / ".join(lines)
            deck.add("对比题", {"type": "qa", "q": entry.get("q"), "a": answer,
                                "source": "derived:contrast", "tags": tags, "key": key})
            continue
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


def build_contrast_plan(pairs_doc: dict, spec: DeckSpec, limit: int = 60) -> dict:
    """把 contrast_seeds.py 的候选折成 plan：每条引用逐字取自源卡答案。"""
    index = source_index(spec)
    cards: list[dict] = []
    seen: set[tuple[str, str, str]] = set()
    for pair in pairs_doc.get("pairs") or []:
        key = str(pair.get("card") or "")
        src = index.get(key)
        if src is None or not src.is_qa:
            continue
        left = pair.get("left") or {}
        right = pair.get("right") or {}
        texts = []
        for side in (left, right):
            raw = normalize(side.get("text", ""))
            if not raw:
                texts.append("")
                continue
            excerpt = pick_excerpt(raw, CONTRAST_MAX_QUOTE) or raw[:CONTRAST_MAX_QUOTE]
            texts.append(normalize(excerpt))
        if any(len(text) < CONTRAST_MIN_QUOTE for text in texts):
            continue
        left_text, right_text = texts
        sig = (key, left_text, right_text)
        if sig in seen:
            continue
        seen.add(sig)
        label_a = normalize(left.get("label", ""))
        label_b = normalize(right.get("label", ""))
        q = normalize(pair.get("prompt", "")) or f"「{label_a}」和「{label_b}」有什么区别？"
        if label_a and label_b:
            answer = f"{label_a}：{left_text}；{label_b}：{right_text}"
        else:
            answer = f"{left_text}；{right_text}"
        cards.append({"type": "contrast", "kind": "claim", "q": q, "a": answer,
                      "sources": [{"key": key, "quote": left_text},
                                  {"key": key, "quote": right_text}],
                      "source_key": key, "source_q": src.q})
        if len(cards) >= limit:
            break
    return {"version": DERIVED_VERSION,
            "source": {"deck": spec.name, "cards": len(index)},
            "options": {"count": 0, "show_source": "short"},
            "cards": cards, "skipped": []}


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
    "干扰项候选请按 derive merge 的格式交回：{\"items\":[{\"source_key\":\"…\",\"distractors\":[\"…\"]}]}，"
    "每张卡最多 2 条，长度与 correct 相差不超过 50%（避免长度泄漏答案），"
    "不得与正确项或已有选项重复；"
    "merge 之后仍需 derive check --allow-model 与人审。"
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
        correct = pick_excerpt(source.answer, MAX_OPTION_CHARS) or ""
        cards.append({
            "source_key": source.key,
            "section": source.section,
            "kind": source.kind,
            "q": source.q,
            "answer": source.answer,
            "correct": correct,
            "correct_chars": len(correct),
            "source": source.card.get("source", ""),
        })
        if limit and len(cards) >= limit:
            break
    return {
        "version": 1,
        "deck": spec.name,
        "instructions": PACKET_INSTRUCTIONS,
        "candidates_format": CANDIDATES_FORMAT,
        "count": len(cards),
        "cards": cards,
    }


def summary(plan: dict) -> str:
    cards = plan.get("cards") or []
    cloze = sum(1 for c in cards if c.get("type") == "cloze")
    contrast = sum(1 for c in cards if c.get("type") == "contrast")
    choice = sum(1 for c in cards if c.get("type") == "choice")
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
    extra = f" / 对比 {contrast}" if contrast else ""
    return (f"填空 {cloze} / 选择 {choice}{extra}；干扰项 {origin_text}；"
            f"未出卡 {len(plan.get('skipped') or [])}（{tail}）")
