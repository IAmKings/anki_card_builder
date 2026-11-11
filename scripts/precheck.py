"""可卡性预检 CLI：`python3 scripts/precheck.py --ingest <manifest.json>`。

只读 ingest 清单，算结构指标（行级）与版面指标（页级），并给出选路建议。
退出码：0 正常、2 用法或清单错误。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ankicards.precheck import analyze, format_report  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="可卡性预检：五个指标定口径")
    parser.add_argument("--ingest", required=True, help="ingest 产物（manifest.json）")
    parser.add_argument("--json", action="store_true", help="输出 JSON，便于脚本消费")
    args = parser.parse_args(argv)

    path = Path(args.ingest)
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        print(f"✗ 读不到清单：{exc}", file=sys.stderr)
        return 2
    except json.JSONDecodeError as exc:
        print(f"✗ 清单不是合法 JSON：{exc}", file=sys.stderr)
        return 2
    if not isinstance(manifest, dict):
        print("✗ 清单顶层必须是对象", file=sys.stderr)
        return 2

    result = analyze(manifest)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(format_report(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
