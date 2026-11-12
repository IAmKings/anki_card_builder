"""从公开源数据重建 Android/MQTT 发布卡组，并用 golden 身份文件校验。

P0 修复的核心：发布物必须由当前 HEAD 的源码和数据构建，而不是上传仓库里
某个历史时点的 output/*.apkg。发布 workflow 与 CI identity job 都调用这个脚本。
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from apkg_identity import compare, read_identity, summary  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
GOLDEN = ROOT / "tests" / "golden" / "public_decks.json"

PUBLIC_DECKS = (
    {
        "key": "android",
        "source": "data/Android",
        "adapter": "android-md",
        "name": "Android面试",
        "out": "Android.apkg",
        "contrast": "data/Android/contrast.json",
        "derived": True,
    },
    {
        "key": "mqtt",
        "source": "data/MQTT",
        "adapter": "mqtt-md",
        "name": "MQTT协议",
        "out": "MQTT.apkg",
        "derived": True,
    },
)


def _run_cli(args: list[str], repo_root: Path) -> None:
    cmd = [sys.executable, "-m", "ankicards", *args]
    proc = subprocess.run(cmd, cwd=repo_root, text=True, capture_output=True)
    if proc.returncode != 0:
        raise RuntimeError(
            f"命令失败: {' '.join(cmd)}\n"
            f"stdout:\n{proc.stdout}\n"
            f"stderr:\n{proc.stderr}"
        )


def _append_contrast(deck_dir: Path, pairs: Path, repo_root: Path) -> int:
    """把卡内条目对比候选折成对比题，作为独立分区并进牌组目录。"""
    with tempfile.TemporaryDirectory(prefix="public-contrast-") as tmp:
        plan = Path(tmp) / "plan_contrast.json"
        compiled = Path(tmp) / "contrast_deck"
        _run_cli(
            ["derive", "contrast", str(pairs), "--deck", str(deck_dir), "--out", str(plan)],
            repo_root,
        )
        _run_cli(
            ["derive", "compile", str(plan), "--deck", str(deck_dir), "--out", str(compiled)],
            repo_root,
        )
        files = sorted((compiled / "cards").glob("*.json"))
        if not files:
            raise RuntimeError(f"对比题编译没有产出卡片: {compiled}")
        cards = []
        for item in files:
            cards.extend(json.loads(item.read_text(encoding="utf-8"))["cards"])
        cards_dir = deck_dir / "cards"
        cards_dir.mkdir(parents=True, exist_ok=True)
        indexes = [int(p.stem) for p in cards_dir.glob("*.json") if p.stem.isdigit()]
        target = cards_dir / f"{max(indexes, default=0) + 1:02d}.json"
        target.write_text(
            json.dumps({"deck": "对比题", "cards": cards}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return len(cards)


def _append_derived(deck_dir: Path, repo_root: Path, options: int = 4) -> int:
    """把选择题/填空题派生分区并进牌组目录（与知识卡同包，独立子牌组）。"""
    with tempfile.TemporaryDirectory(prefix="public-derived-") as tmp:
        plan = Path(tmp) / "plan_derive.json"
        compiled = Path(tmp) / "derived_deck"
        _run_cli(
            ["derive", "plan", "--deck", str(deck_dir), "--out", str(plan), "--options", str(options)],
            repo_root,
        )
        _run_cli(["derive", "check", str(plan), "--deck", str(deck_dir)], repo_root)
        _run_cli(
            ["derive", "compile", str(plan), "--deck", str(deck_dir), "--out", str(compiled)],
            repo_root,
        )
        files = sorted((compiled / "cards").glob("*.json"))
        if not files:
            raise RuntimeError(f"派生编译没有产出卡片: {compiled}")
        cards_dir = deck_dir / "cards"
        cards_dir.mkdir(parents=True, exist_ok=True)
        indexes = [int(p.stem) for p in cards_dir.glob("*.json") if p.stem.isdigit()]
        next_index = max(indexes, default=0)
        total = 0
        for item in files:
            payload = json.loads(item.read_text(encoding="utf-8"))
            next_index += 1
            (cards_dir / f"{next_index:02d}.json").write_text(
                json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
            total += len(payload.get("cards") or [])
        return total


def build_all(out_dir: Path, repo_root: Path = ROOT) -> dict[str, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    built: dict[str, Path] = {}
    for deck in PUBLIC_DECKS:
        with tempfile.TemporaryDirectory(prefix=f"public-{deck['key']}-") as tmp:
            deck_dir = Path(tmp) / "deck"
            _run_cli(
                [
                    "import",
                    str(repo_root / deck["source"]),
                    "--adapter",
                    deck["adapter"],
                    "--out",
                    str(deck_dir),
                    "--name",
                    deck["name"],
                ],
                repo_root,
            )
            if deck.get("contrast"):
                _append_contrast(deck_dir, repo_root / deck["contrast"], repo_root)
            if deck.get("derived"):
                _append_derived(deck_dir, repo_root)
            out_path = out_dir / deck["out"]
            _run_cli(
                ["build", str(deck_dir), "--out", str(out_path)],
                repo_root,
            )
            _run_cli(["verify", str(out_path)], repo_root)
            built[deck["key"]] = out_path
    return built


def identities(built: dict[str, Path]) -> dict[str, dict]:
    return {key: summary(read_identity(path)) for key, path in built.items()}


def write_golden(data: dict[str, dict], path: Path = GOLDEN) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"schema": 1, "decks": data}, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )


def load_golden(path: Path = GOLDEN) -> dict[str, dict]:
    if not path.exists():
        raise RuntimeError(f"缺少 golden 文件: {path}；先运行 --write-golden")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema") != 1 or "decks" not in payload:
        raise RuntimeError(f"golden 文件格式不对: {path}")
    return payload["decks"]


def check_golden(actual: dict[str, dict], expected: dict[str, dict]) -> list[str]:
    failures: list[str] = []
    for key in sorted(set(actual) | set(expected)):
        if key not in actual:
            failures.append(f"{key}: golden 有、本次构建缺失")
            continue
        if key not in expected:
            failures.append(f"{key}: 本次构建有、golden 缺失")
            continue
        # JSON 读回的 deck_ids 是 list，而内存里是 tuple；统一成 JSON 形态再比。
        a = json.loads(json.dumps(actual[key], ensure_ascii=False))
        e = json.loads(json.dumps(expected[key], ensure_ascii=False))
        for field in ("notes", "cards", "guid_count", "guid_sha256", "models",
                      "model_ids", "deck_names", "deck_ids"):
            if a.get(field) != e.get(field):
                failures.append(f"{key}.{field}: golden={e.get(field)!r} actual={a.get(field)!r}")
    return failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="从公开源重建 Android/MQTT 卡组")
    parser.add_argument("--out", default="dist", help="输出目录（默认 dist）")
    parser.add_argument("--repo-root", default=str(ROOT), help=argparse.SUPPRESS)
    parser.add_argument("--write-golden", action="store_true", help="写入 golden 身份文件")
    parser.add_argument("--check-golden", action="store_true", help="与 golden 比对")
    parser.add_argument("--json", action="store_true", help="只输出 JSON 摘要")
    args = parser.parse_args(argv)

    repo_root = Path(args.repo_root).resolve()
    out_dir = Path(args.out)
    if not out_dir.is_absolute():
        out_dir = repo_root / out_dir

    built = build_all(out_dir, repo_root)
    actual = identities(built)

    if args.write_golden:
        write_golden(actual)
        print(f"已写入 golden: {GOLDEN}", file=sys.stderr)

    if args.json:
        print(json.dumps(actual, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        for key, path in built.items():
            print(f"{key}: {path}  notes={actual[key]['notes']}  "
                  f"cards={actual[key]['cards']}  guids={actual[key]['guid_count']}")

    if args.check_golden:
        failures = check_golden(actual, load_golden())
        if failures:
            print("✗ golden 身份校验失败：", file=sys.stderr)
            for item in failures:
                print(f"  - {item}", file=sys.stderr)
            return 1
        print("✓ golden 身份校验通过", file=sys.stderr)

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print(f"✗ {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
