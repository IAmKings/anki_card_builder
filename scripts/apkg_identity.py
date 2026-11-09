"""读取 .apkg 的「身份」：guid 集合、笔记/卡片数、模型字段、牌组名。

P0 的发布问题不是文件损坏，而是「发布物与 HEAD 不同源」。这个脚本只读
apkg，不依赖 genanki，可用于发布前比对、证据采集和 golden 校验。
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
import tempfile
import zipfile
from pathlib import Path

COLLECTIONS = ("collection.anki21", "collection.anki2", "collection.anki21b")


def _open_collection(root: Path) -> sqlite3.Connection:
    for name in COLLECTIONS:
        path = root / name
        if path.exists():
            con = sqlite3.connect(str(path))
            con.text_factory = str
            return con
    raise ValueError(f"apkg 里找不到 collection 数据库: {sorted(p.name for p in root.iterdir())}")


def read_identity(path: str | Path) -> dict:
    """返回 apkg 的完整身份；guids 保持排序，summary() 会折叠成稳定摘要。"""
    path = Path(path)
    raw = path.read_bytes()
    with zipfile.ZipFile(path) as archive:
        bad = archive.testzip()
        if bad is not None:
            raise ValueError(f"apkg 的 zip 损坏: {bad}")
        with tempfile.TemporaryDirectory(prefix="apkg-identity-") as tmp:
            archive.extractall(tmp)
            con = _open_collection(Path(tmp))
            try:
                models_raw, decks_raw = con.execute("select models,decks from col").fetchone()
                models = {str(k): v for k, v in json.loads(models_raw).items()}
                decks = {int(k): v for k, v in json.loads(decks_raw).items()}
                notes = con.execute("select guid,mid,flds from notes").fetchall()
                cards = con.execute("select nid,did,ord from cards").fetchall()
            finally:
                con.close()

    models_by_name = {
        str(model.get("name", mid)): [str(f.get("name", "")) for f in model.get("flds", [])]
        for mid, model in models.items()
    }
    model_ids = {str(mid): str(model.get("name", "")) for mid, model in models.items()}
    deck_names = sorted(str(d.get("name", "")) for d in decks.values() if d.get("name"))
    deck_ids = sorted((int(did), str(d.get("name", ""))) for did, d in decks.items()
                      if d.get("name"))
    return {
        "path": str(path),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "bytes": len(raw),
        "notes": len(notes),
        "cards": len(cards),
        "guids": sorted(str(n[0]) for n in notes),
        "models": models_by_name,
        "model_ids": model_ids,
        "deck_names": deck_names,
        "deck_ids": deck_ids,
    }


def summary(identity: dict) -> dict:
    """可写入 golden 的稳定摘要；不保存完整 guid 列表。"""
    joined = "\n".join(identity["guids"]).encode("utf-8")
    return {
        "notes": identity["notes"],
        "cards": identity["cards"],
        "guid_count": len(identity["guids"]),
        "guid_sha256": hashlib.sha256(joined).hexdigest(),
        "models": identity["models"],
        "model_ids": identity["model_ids"],
        "deck_names": identity["deck_names"],
        "deck_ids": identity["deck_ids"],
    }


def compare(expected: dict, actual: dict) -> dict:
    exp = set(expected["guids"])
    act = set(actual["guids"])
    return {
        "expected_sha256": expected["sha256"],
        "actual_sha256": actual["sha256"],
        "expected_notes": expected["notes"],
        "actual_notes": actual["notes"],
        "expected_cards": expected["cards"],
        "actual_cards": actual["cards"],
        "expected_models": expected["models"],
        "actual_models": actual["models"],
        "expected_model_ids": expected["model_ids"],
        "actual_model_ids": actual["model_ids"],
        "expected_decks": expected["deck_names"],
        "actual_decks": actual["deck_names"],
        "expected_deck_ids": expected["deck_ids"],
        "actual_deck_ids": actual["deck_ids"],
        "guid_intersection": len(exp & act),
        "expected_guid_count": len(exp),
        "actual_guid_count": len(act),
    }


def print_summary(identity: dict) -> None:
    s = summary(identity)
    print(json.dumps({
        "path": identity["path"],
        "sha256": identity["sha256"],
        "bytes": identity["bytes"],
        **s,
    }, ensure_ascii=False, indent=2))


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="读取/比较 .apkg 身份")
    parser.add_argument("apkg", nargs="+", help="一个 apkg（打印摘要）或两个 apkg（比较）")
    parser.add_argument("--json", action="store_true", help="只输出 JSON")
    args = parser.parse_args(argv)

    identities = [read_identity(p) for p in args.apkg]
    if len(identities) == 1:
        if args.json:
            print(json.dumps({"path": identities[0]["path"], **summary(identities[0])},
                             ensure_ascii=False, indent=2))
        else:
            print_summary(identities[0])
        return 0
    if len(identities) != 2:
        parser.error("最多比较两个 apkg")

    result = compare(*identities)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"old: {result['expected_sha256']}  notes={result['expected_notes']}  "
              f"cards={result['expected_cards']}  guids={result['expected_guid_count']}")
        print(f"new: {result['actual_sha256']}  notes={result['actual_notes']}  "
              f"cards={result['actual_cards']}  guids={result['actual_guid_count']}")
        print(f"guid 交集: {result['guid_intersection']} / "
              f"{result['expected_guid_count']} / {result['actual_guid_count']}")
        print(f"old models: {result['expected_models']}")
        print(f"new models: {result['actual_models']}")
        print(f"old model ids: {result['expected_model_ids']}")
        print(f"new model ids: {result['actual_model_ids']}")
        print(f"old decks: {result['expected_decks']}")
        print(f"new decks: {result['actual_decks']}")
        print(f"old deck ids: {result['expected_deck_ids']}")
        print(f"new deck ids: {result['actual_deck_ids']}")
        if result["guid_intersection"] == 0:
            print("⚠ 两包没有任何共同 guid：这是两套独立卡组，不能覆盖升级。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
