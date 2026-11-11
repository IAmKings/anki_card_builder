#!/usr/bin/env python3
"""把一份牌组投影成语义地图：邻居、簇、中心度、近重复、孤立点。

只读牌组，不写卡片、不改 plan、不进 CI。
依赖（独立于 requirements.txt）：numpy、tokenizers、onnxruntime、networkx。
模型默认用 Xenova/bge-small-zh-v1.5 的 ONNX 导出，由用户自己放到本地目录。

示例：
  python3 scripts/semantic_map.py --deck data/Android --out-dir .work/semantic
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import math
import re
import sys
import time
from collections import Counter
from pathlib import Path

VERSION = 1
DEFAULT_THRESHOLD = 0.60
DEFAULT_TOP_K = 5
DEFAULT_DUP = 0.90
DEFAULT_RESOLUTION = 1.0
DEFAULT_MODEL = Path.home() / ".cache" / "bge-small-zh-v1.5"
MAX_TOKENS = 512
ASCII_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9_.+#/-]{1,}")
CJK_RUN_RE = re.compile(r"[\u4e00-\u9fff]+")
LABEL_STOP = {
    "什么", "如何", "哪些", "怎么", "为什", "是否", "可以", "需要", "如果", "因为",
    "所以", "以及", "之间", "一个", "我们", "时候", "情况", "详细", "解释", "不允许",
}
LABEL_SPLIT = set(
    "的了吗呢吧啊是就都也又很和与及或在中对把被从向于其之而且但若这那哪个将"
    "要会能你我他她它些"
)


def fail(message: str) -> int:
    print(f"✗ {message}", file=sys.stderr)
    return 2


def plain(text) -> str:
    """去 HTML 标签并归一空白；与 ankicards.derive.plain 保持同样的两次反转义。"""
    s = html.unescape(str(text or ""))
    s = re.sub(r"<[^>]+>", " ", s)
    s = html.unescape(s)
    return re.sub(r"\s+", " ", s).strip()


def load_cards(deck_dir: Path) -> list[dict]:
    files = sorted((deck_dir / "cards").glob("*.json"))
    if not files:
        raise SystemExit(f"✗ {deck_dir} 里没有 cards/*.json")
    cards = []
    for path in files:
        data = json.loads(path.read_text(encoding="utf-8"))
        section = data.get("deck", path.stem)
        for index, card in enumerate(data.get("cards", [])):
            key = card.get("key")
            if not isinstance(key, str) or not key:
                seed = f"{section}|{card.get('q', '')}|{card.get('a', '')}"
                key = hashlib.sha1(seed.encode("utf-8")).hexdigest()[:12]
            cards.append({
                "key": key,
                "section": section,
                "q": plain(card.get("q", "")),
                "a": plain(card.get("a", "")),
                "index": index,
            })
    return cards


def find_model(model_dir: Path) -> tuple[Path, Path]:
    tokenizer = model_dir / "tokenizer.json"
    if not tokenizer.exists():
        tokenizer = model_dir / "onnx" / "tokenizer.json"
    for candidate in (model_dir / "onnx" / "model.onnx", model_dir / "model.onnx"):
        if candidate.exists():
            model = candidate
            break
    else:
        raise SystemExit(
            f"✗ 在 {model_dir} 找不到 model.onnx\n"
            "  下载（一次性，约 95MB）：\n"
            "    huggingface-cli download Xenova/bge-small-zh-v1.5 \\\n"
            f"      --local-dir {model_dir}\n"
            "  或用 --model 指向已有的模型目录。"
        )
    if not tokenizer.exists():
        raise SystemExit(f"✗ 在 {model_dir} 找不到 tokenizer.json")
    return tokenizer, model


def require_deps():
    try:
        import numpy as np  # noqa: F401
    except ImportError as exc:
        raise SystemExit(
            f"✗ 缺少依赖 {exc.name}：pip install -r requirements-rag.txt"
        ) from exc
    try:
        from tokenizers import Tokenizer  # noqa: F401
        import onnxruntime as ort  # noqa: F401
    except ImportError as exc:
        raise SystemExit(
            f"✗ 缺少依赖 {exc.name}：pip install -r requirements-rag.txt"
        ) from exc
    try:
        import networkx as nx  # noqa: F401
    except ImportError as exc:
        raise SystemExit(
            f"✗ 缺少依赖 {exc.name}：pip install -r requirements-rag.txt"
        ) from exc


def encode(texts: list[str], tokenizer, session, batch: int = 32, quiet: bool = False):
    import numpy as np

    names = {item.name for item in session.get_inputs()}
    vectors = []
    started = time.time()
    for start in range(0, len(texts), batch):
        encoded = tokenizer.encode_batch(texts[start:start + batch])
        ids = np.array([item.ids for item in encoded], dtype=np.int64)
        mask = np.array([item.attention_mask for item in encoded], dtype=np.int64)
        feed = {"input_ids": ids, "attention_mask": mask}
        if "token_type_ids" in names:
            feed["token_type_ids"] = np.zeros_like(ids)
        output = session.run(None, feed)[0]
        hidden = output[:, 0, :].astype(np.float32)
        hidden /= np.linalg.norm(hidden, axis=1, keepdims=True) + 1e-12
        vectors.append(hidden)
        if not quiet and start and start % 512 == 0:
            print(f"  编码 {start}/{len(texts)}（{time.time() - started:.0f}s）", flush=True)
    return np.vstack(vectors)


def mutual_edges(similarity, threshold: float, top_k: int) -> list[tuple[int, int, float]]:
    import numpy as np

    order = np.argsort(-similarity, axis=1)
    tops = [set(int(x) for x in order[i, 1:top_k + 1]) for i in range(len(order))]
    edges = {}
    for i in range(len(order)):
        for j in order[i, 1:top_k + 1]:
            j = int(j)
            if i in tops[j] and similarity[i, j] >= threshold:
                a, b = (i, j) if i < j else (j, i)
                edges[(a, b)] = max(edges.get((a, b), 0.0), float(similarity[i, j]))
    return [(a, b, w) for (a, b), w in sorted(edges.items())]


def louvain_clusters(edges, size: int, resolution: float) -> list[list[int]]:
    import networkx as nx

    graph = nx.Graph()
    graph.add_nodes_from(range(size))
    for a, b, weight in edges:
        graph.add_edge(a, b, weight=weight)
    communities = nx.community.louvain_communities(
        graph, weight="weight", resolution=resolution, seed=7
    )
    return sorted(
        (sorted(community) for community in communities),
        key=lambda members: (-len(members), members[0]),
    )


def _tokens(text: str) -> set[str]:
    """按虚词切块取 2–6 字候选词；中文没有分词器时，这比 n-gram 干净得多。"""
    tokens: set[str] = set()
    for run in CJK_RUN_RE.findall(text):
        buffer = ""
        for char in run:
            if char in LABEL_SPLIT:
                if 2 <= len(buffer) <= 6:
                    tokens.add(buffer)
                buffer = ""
            else:
                buffer += char
        if 2 <= len(buffer) <= 6:
            tokens.add(buffer)
    for token in list(tokens):
        if any(stop in token for stop in LABEL_STOP):
            tokens.discard(token)
    return tokens


def cluster_label(members: list[int], token_sets: list[set[str]],
                  document_frequency: Counter, clusters: int) -> str:
    counts = Counter()
    for index in members:
        counts.update(token_sets[index])
    scored = []
    for token, count in counts.items():
        if count < 2 or token.isdigit():
            continue
        df = document_frequency[token]
        if df > clusters / 2:
            continue
        score = count * math.log((clusters + 1) / (df + 1)) * (1.0 + 0.12 * (len(token) - 2))
        scored.append((score, token))
    scored.sort(key=lambda item: (-item[0], item[1]))
    picked: list[str] = []
    for _, token in scored:
        if any(token in existing or existing in token for existing in picked):
            continue
        picked.append(token)
        if len(picked) == 3:
            break
    return " / ".join(picked) if picked else "（无显著共性）"


def build_report(cards: list[dict], similarity, edges, clusters, params, model) -> dict:
    import numpy as np

    size = len(cards)
    membership = {}
    for cluster_id, members in enumerate(clusters, start=1):
        for index in members:
            membership[index] = cluster_id

    token_sets = [_tokens(card["q"] + " " + card["a"]) for card in cards]
    document_frequency = Counter()
    for tokens in token_sets:
        document_frequency.update(tokens)

    cluster_rows = []
    for cluster_id, members in enumerate(clusters, start=1):
        sections = Counter(cards[i]["section"] for i in members)
        cluster_rows.append({
            "id": f"c{cluster_id}",
            "size": len(members),
            "label": cluster_label(members, token_sets, document_frequency, len(clusters)),
            "sections": [{"name": name, "count": count} for name, count in sections.most_common(3)],
            "cards": [cards[i]["key"] for i in members],
            "sample": [cards[i]["q"][:80] for i in members[:3]],
        })

    order = np.argsort(-similarity, axis=1)
    neighbors = []
    for i in range(size):
        top = [
            {"key": cards[int(j)]["key"], "score": round(float(similarity[i, j]), 3)}
            for j in order[i, 1:params["top_k"] + 1]
        ]
        neighbors.append({"key": cards[i]["key"], "q": cards[i]["q"][:80], "top": top})

    duplicates = []
    for i in range(size):
        for j in range(i + 1, size):
            score = float(similarity[i, j])
            if score >= params["dup_threshold"]:
                duplicates.append({
                    "a": cards[i]["key"], "b": cards[j]["key"], "score": round(score, 3),
                    "qa": cards[i]["q"][:60], "qb": cards[j]["q"][:60],
                })
    duplicates.sort(key=lambda row: (-row["score"], row["a"], row["b"]))

    import numpy as np

    rank = np.full(size, 1.0 / size, dtype=np.float64)
    if edges:
        src = np.array([a for a, _, _ in edges] + [b for _, b, _ in edges], dtype=np.int64)
        dst = np.array([b for _, b, _ in edges] + [a for a, _, _ in edges], dtype=np.int64)
        weight = np.array([w for _, _, w in edges] * 2, dtype=np.float64)
        out_weight = np.zeros(size, dtype=np.float64)
        np.add.at(out_weight, src, weight)
        for _ in range(100):
            contrib = np.zeros(size, dtype=np.float64)
            np.add.at(contrib, dst, rank[src] * weight / out_weight[src])
            updated = (1.0 - 0.85) / size + 0.85 * contrib
            dangling = out_weight == 0
            if dangling.any():
                updated += 0.85 * rank[dangling].sum() / size
            if np.abs(updated - rank).sum() < 1e-10:
                rank = updated
                break
            rank = updated
    ranked = sorted(((index, float(score)) for index, score in enumerate(rank)),
                    key=lambda item: (-item[1], item[0]))
    centrality_rows = [
        {"key": cards[index]["key"], "q": cards[index]["q"][:80], "score": round(float(score), 5),
         "cluster": f"c{membership.get(index, 0)}"}
        for index, score in ranked[:params["centrality"]]
    ]

    singletons = [cards[members[0]]["key"] for members in clusters if len(members) == 1]

    return {
        "version": VERSION,
        "deck": {"cards": size, "sections": len({card["section"] for card in cards})},
        "model": model,
        "params": params,
        "cards": [
            {"key": card["key"], "section": card["section"], "q": card["q"][:200],
             "cluster": f"c{membership[index]}"}
            for index, card in enumerate(cards)
        ],
        "clusters": cluster_rows,
        "neighbors": neighbors,
        "duplicates": duplicates,
        "centrality": centrality_rows,
        "singletons": singletons,
        "stats": {
            "clusters": len(clusters),
            "edges": len(edges),
            "singletons": len(singletons),
            "duplicates": len(duplicates),
            "largest": max((len(members) for members in clusters), default=0),
        },
    }


def format_markdown(report: dict, elapsed: float) -> str:
    stats = report["stats"]
    params = report["params"]
    model = report["model"]
    lines = [
        "# 语义地图",
        "",
        f"- 牌组：{report['deck']['cards']} 张 / {report['deck']['sections']} 个 section",
        f"- 模型：`{model['name']}`（sha256 {model['sha256'][:16]}…）",
        f"- 参数：τ={params['threshold']}、top-{params['top_k']}、重复≥{params['dup_threshold']}、resolution={params['resolution']}",
        f"- 结果：{stats['clusters']} 簇 / {stats['edges']} 条边 / {stats['duplicates']} 对近重复 / "
        f"{stats['singletons']} 个孤立点 / 最大簇 {stats['largest']}",
        f"- 耗时：{elapsed:.0f}s",
        "",
        "## 簇",
        "",
        "| 簇 | 大小 | 标签 | 主要 section | 示例 |",
        "|---|---|---|---|---|",
    ]
    for cluster in report["clusters"][:20]:
        sections = "、".join(f"{row['name']}({row['count']})" for row in cluster["sections"])
        sample = cluster["sample"][0].replace("|", "\\|") if cluster["sample"] else ""
        lines.append(f"| {cluster['id']} | {cluster['size']} | {cluster['label']} | {sections} | {sample} |")
    lines += ["", "## 近重复", ""]
    if report["duplicates"]:
        for row in report["duplicates"][:20]:
            lines.append(f"- {row['score']:.3f}：{row['qa']} ⇄ {row['qb']}")
    else:
        lines.append("- 无")
    lines += ["", "## 中心度 Top 10", ""]
    for row in report["centrality"][:10]:
        lines.append(f"- {row['score']:.4f} [{row['cluster']}] {row['q']}")
    lines += ["", "## 孤立点（无互惠近邻）", ""]
    lines.append(f"- 共 {stats['singletons']} 个" if stats["singletons"] else "- 无")
    return "\n".join(lines) + "\n"


def run(args) -> int:
    require_deps()
    import numpy as np
    import onnxruntime as ort
    from tokenizers import Tokenizer

    started = time.time()
    deck = Path(args.deck)
    if not deck.is_dir():
        return fail(f"{deck} 不是目录")
    cards = load_cards(deck)
    if args.limit:
        cards = cards[:args.limit]
    if not cards:
        return fail("牌组里没有卡片")

    model_dir = Path(args.model).expanduser() if args.model else DEFAULT_MODEL
    tokenizer_path, model_path = find_model(model_dir)
    tokenizer = Tokenizer.from_file(str(tokenizer_path))
    tokenizer.enable_truncation(max_length=MAX_TOKENS)
    tokenizer.enable_padding(pad_id=0, pad_token="[PAD]")
    session = ort.InferenceSession(str(model_path), providers=["CPUExecutionProvider"])

    texts = [card["q"] + " " + card["a"] for card in cards]
    if not args.quiet:
        print(f"编码 {len(texts)} 张卡（{args.model or DEFAULT_MODEL}）…", flush=True)
    embeddings = encode(texts, tokenizer, session, quiet=args.quiet)
    import warnings

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)  # Accelerate BLAS 的假 overflow 提示
        similarity = embeddings @ embeddings.T

    edges = mutual_edges(similarity, args.threshold, args.top_k)
    clusters = louvain_clusters(edges, len(cards), args.resolution)
    model = {
        "name": "bge-small-zh-v1.5",
        "path": str(model_path),
        "sha256": hashlib.sha256(model_path.read_bytes()).hexdigest(),
        "dim": int(embeddings.shape[1]),
    }
    params = {
        "threshold": args.threshold,
        "top_k": args.top_k,
        "dup_threshold": args.dup_threshold,
        "resolution": args.resolution,
        "centrality": args.centrality,
    }
    report = build_report(cards, similarity, edges, clusters, params, model)
    elapsed = time.time() - started

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    json_path = out / "semantic.json"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    stats = report["stats"]
    print(
        f"✓ {stats['clusters']} 簇 / {stats['edges']} 条边 / {stats['duplicates']} 对近重复 / "
        f"{stats['singletons']} 个孤立点（{elapsed:.0f}s）"
    )
    print(f"  {json_path}")
    if not args.json_only:
        md_path = out / "semantic.md"
        md_path.write_text(format_markdown(report, elapsed), encoding="utf-8")
        print(f"  {md_path}")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="牌组 → 语义地图（kNN、Louvain 簇、中心度、近重复）")
    parser.add_argument("--deck", required=True, help="牌组目录（含 deck.json 与 cards/）")
    parser.add_argument("--model", help="本地模型目录（含 tokenizer.json 与 onnx/model.onnx）")
    parser.add_argument("--out-dir", default=".work/semantic", help="输出目录（默认 .work/semantic）")
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD, help="建图的余弦阈值")
    parser.add_argument("--top-k", type=int, default=DEFAULT_TOP_K, help="每张卡保留的近邻数")
    parser.add_argument("--dup-threshold", type=float, default=DEFAULT_DUP, help="判为近重复的余弦阈值")
    parser.add_argument("--resolution", type=float, default=DEFAULT_RESOLUTION, help="Louvain 分辨率")
    parser.add_argument("--centrality", type=int, default=20, help="中心度输出条数")
    parser.add_argument("--limit", type=int, help="只处理前 N 张（调试用）")
    parser.add_argument("--json-only", action="store_true", help="不写 semantic.md")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)
    try:
        return run(args)
    except KeyboardInterrupt:
        return fail("已中断")
    except SystemExit:
        raise


if __name__ == "__main__":
    sys.exit(main())
