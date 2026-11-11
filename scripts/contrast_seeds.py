#!/usr/bin/env python3
"""从 seeds.json 挑「对比题」候选：同簇、相似度高、题干不同。

只产出候选（JSON + Markdown），不写卡、不改 plan。
对比题的答案要同时引用两张卡，compilation 需要多引用契约（未实现），
所以这里只做「值得对比哪两题」的选题，实际出题仍走人审或模型写、plan 校验。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from semantic_map import load_cards  # noqa: E402

MIN_SCORE = 0.72
MAX_PER_CARD = 1
ITEM_SPLIT = re.compile(r"[•·]\s*|\n+")
LABEL = re.compile(r"^\s*([^：:]{2,30})[：:]\s*(.+)$", re.S)
STOP_LABELS = {
    "概念", "定义", "优点", "缺点", "特点", "原理", "好处", "优势", "劣势",
    "适用场景", "应用场景", "实现方式", "注意事项", "四个必要条件", "性能好",
    "安全性高", "稳定易用",
}


def load_seeds(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("version") != 1 or not isinstance(data.get("cards"), dict):
        raise SystemExit(f"✗ {path} 不是 semantic_map.py 产出的 seeds.json（需要 version=1 与 cards 对象）")
    return data


def _best(entry: dict) -> str:
    items = entry.get("neighbors") or []
    if not items:
        return ""
    return max(items, key=lambda n: float(n.get("score") or 0)).get("key", "")


def pick_pairs(cards: list[dict], seeds: dict, min_score: float = MIN_SCORE,
               per_card: int = MAX_PER_CARD, limit: int = 60,
               mutual_only: bool = True) -> list[dict]:
    """每张卡最多贡献 per_card 对；无序对去重；同簇且分数达标才算候选。"""
    by_key = {c["key"]: c for c in cards}
    labels = {c.get("id"): c.get("label", "") for c in seeds.get("clusters") or []}
    seen: set[tuple[str, str]] = set()
    pairs: list[dict] = []
    for card in cards:
        entry = (seeds.get("cards") or {}).get(card["key"]) or {}
        cluster = entry.get("cluster")
        chosen = 0
        neighbors = sorted(entry.get("neighbors") or [], key=lambda n: -(float(n.get("score") or 0)))
        for item in neighbors:
            if chosen >= per_card:
                break
            try:
                score = float(item.get("score") or 0)
            except (TypeError, ValueError):
                continue
            if score < min_score:
                continue
            other = by_key.get(item.get("key"))
            if not other or not other["q"] or other["q"] == card["q"]:
                continue
            other_entry = (seeds.get("cards") or {}).get(other["key"]) or {}
            if cluster and other_entry.get("cluster") and other_entry["cluster"] != cluster:
                continue
            pair = tuple(sorted((card["key"], other["key"])))
            if pair in seen:
                continue
            seen.add(pair)
            pairs.append({
                "id": f"p{len(pairs) + 1}",
                "cluster": cluster,
                "label": labels.get(cluster, ""),
                "score": round(score, 4),
                "a": {"key": card["key"], "q": card["q"], "answer": card["a"][:300]},
                "b": {"key": other["key"], "q": other["q"], "answer": other["a"][:300]},
            })
            chosen += 1
    if mutual_only:
        best = {k: _best(v) for k, v in (seeds.get("cards") or {}).items()}
        pairs = [p for p in pairs if best.get(p["a"]["key"]) == p["b"]["key"]
                 and best.get(p["b"]["key"]) == p["a"]["key"]]
    pairs.sort(key=lambda p: (-p["score"], p["a"]["key"]))
    return pairs[:limit]




def split_items(answer: str) -> list[dict]:
    """把「A：…• B：…• C：…」这类答案拆成带标签的条目；没有标签就不算。"""
    items = []
    for part in ITEM_SPLIT.split(answer or ""):
        part = part.strip()
        if not part or len(part) > 220:
            continue
        match = LABEL.match(part)
        if match:
            label = match.group(1).strip()
            text = match.group(2).strip()
            if (1 < len(label) <= 30 and len(text) >= 4
                    and label not in STOP_LABELS and not re.search(r"(好|高|易用)$", label)):
                items.append({"label": label, "text": text})
    return items


def pick_item_pairs(cards: list[dict], per_card: int = 2, limit: int = 60) -> list[dict]:
    """同一张卡的答案里，相邻两个带标签条目 → 一道「A 和 B 有什么区别」候选。"""
    pairs: list[dict] = []
    for card in cards:
        items = split_items(card["a"])
        made = 0
        for left, right in zip(items, items[1:]):
            if made >= per_card:
                break
            pairs.append({
                "id": f"i{len(pairs) + 1}",
                "type": "intra-card",
                "card": card["key"],
                "context": card["q"],
                "left": left,
                "right": right,
                "prompt": f"「{left['label']}」和「{right['label']}」有什么区别？",
            })
            made += 1
    return pairs[:limit]

def format_item_markdown(pairs: list[dict], deck: str) -> str:
    lines = [f"# 对比题候选（卡内条目）：{deck}", "", f"共 {len(pairs)} 对。", ""]
    for p in pairs:
        lines.append(f"## {p['id']} · {p['context']}")
        lines.append(f"- {p['left']['label']}：{p['left']['text'][:120]}")
        lines.append(f"- {p['right']['label']}：{p['right']['text'][:120]}")
        lines.append(f"- 建议问法：{p['prompt']}")
        lines.append("")
    return "\n".join(lines)


def format_markdown(pairs: list[dict], deck: str) -> str:
    lines = [f"# 对比题候选：{deck}", "", f"共 {len(pairs)} 对；每对同簇、余弦达标、题干不同。", ""]
    for p in pairs:
        label = f"（{p['label']}）" if p["label"] else ""
        lines.append(f"## {p['id']}{label} · 相似度 {p['score']}")
        lines.append(f"- A：{p['a']['q']}")
        lines.append(f"- B：{p['b']['q']}")
        lines.append(f"- 建议问法：「A」和「B」有什么区别？各自适用于什么场景？")
        lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="从 seeds.json 挑对比题候选")
    parser.add_argument("--seeds", required=True, help="semantic_map.py 产出的 seeds.json")
    parser.add_argument("--deck", required=True, help="源牌组目录")
    parser.add_argument("--out", default=".work/semantic/contrast.json", help="输出 JSON（默认 .work/semantic/contrast.json）")
    parser.add_argument("--min-score", type=float, default=MIN_SCORE)
    parser.add_argument("--per-card", type=int, default=MAX_PER_CARD)
    parser.add_argument("--limit", type=int, default=60, help="最多输出多少对（按相似度降序）")
    parser.add_argument("--no-mutual", action="store_true", help="不要求互为最近邻")
    parser.add_argument("--mode", choices=["list", "neighbor", "both"], default="list",
                        help="list=卡内条目对比（默认）；neighbor=跨卡邻居；both=两者")
    parser.add_argument("--per-card-items", type=int, default=2, help="卡内最多取几对相邻条目")
    args = parser.parse_args(argv)

    seeds = load_seeds(Path(args.seeds))
    cards = load_cards(Path(args.deck))
    pairs = []
    if args.mode in ("list", "both"):
        pairs = pick_item_pairs(cards, args.per_card_items, args.limit)
    else:
        pairs = pick_pairs(cards, seeds, args.min_score, args.per_card,
                           args.limit, not args.no_mutual)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"version": 1, "deck": seeds.get("deck", ""),
                               "params": {"mode": args.mode, "min_score": args.min_score,
                                          "per_card": args.per_card, "limit": args.limit},
                               "pairs": pairs}, ensure_ascii=False, indent=1), encoding="utf-8")
    md = out.with_suffix(".md")
    body = format_item_markdown(pairs, seeds.get("deck", "")) if args.mode in ("list", "both") \
        else format_markdown(pairs, seeds.get("deck", ""))
    md.write_text(body, encoding="utf-8")
    print(f"✓ {len(pairs)} 对对比题候选：{out} / {md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
