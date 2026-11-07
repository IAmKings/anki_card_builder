"""命令行入口：check / build / verify。

    python3 -m ankicards check  <deck-dir> [--pdf 手册.pdf]
    python3 -m ankicards build  <deck-dir> --out output/xxx.apkg [--pdf 手册.pdf] [--lite]
    python3 -m ankicards verify <xxx.apkg> [--json]

退出码：0 成功；1 校验/验证失败；2 用法或环境错误。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .build import build
from .preview import build_preview
from .schema import load_spec, validate
from .verify import verify


def _pdf_info(pdf: str | None):
    if not pdf:
        return None, None
    try:
        import pymupdf  # type: ignore
    except ImportError:
        print("提示：未安装 pymupdf，跳过页码/裁图越界检查（pip install pymupdf）")
        return None, None
    doc = pymupdf.open(pdf)
    try:
        return doc.page_count, (doc[0].rect.width, doc[0].rect.height)
    finally:
        doc.close()


def cmd_check(args) -> int:
    spec = load_spec(args.deck, args.name)
    page_count, page_size = _pdf_info(args.pdf)
    report = validate(spec, page_count=page_count, page_size=page_size)
    print(f"牌组 {spec.name}：{len(spec.sections)} 个子牌组 / {spec.card_count} 张卡片")
    for warning in report.warnings:
        print(f"  ⚠ {warning}")
    for error in report.errors:
        print(f"  ✗ {error}")
    print("校验通过" if report.ok else f"校验失败：{len(report.errors)} 个错误")
    return 0 if report.ok else 1


def cmd_build(args) -> int:
    spec = load_spec(args.deck, args.name)
    page_count, page_size = _pdf_info(args.pdf)
    report = validate(spec, page_count=page_count, page_size=page_size)
    for warning in report.warnings[:10]:
        print(f"  ⚠ {warning}")
    if not report.ok:
        for error in report.errors:
            print(f"  ✗ {error}")
        print("构建中止：先修数据")
        return 1
    stats = build(spec, args.out, pdf=args.pdf, lite=args.lite)
    print(json.dumps(stats, ensure_ascii=False, indent=1))
    if args.preview:
        preview = build_preview(spec, args.preview, pdf=args.pdf)
        print(f"预览：{preview}（{preview.stat().st_size / 1048576:.1f} MB）")
    return 0


def cmd_import(args) -> int:
    from .adapters import ADAPTERS, write_deck

    if args.list:
        for name in sorted(ADAPTERS):
            print(name)
        return 0
    if not args.adapter:
        print(f"请指定 --adapter；可用：{', '.join(sorted(ADAPTERS))}")
        return 2
    func = ADAPTERS.get(args.adapter)
    if func is None:
        print(f"未知 adapter: {args.adapter}；可用：{', '.join(sorted(ADAPTERS))}")
        return 2
    deck = func(Path(args.source)) if not args.name else func(Path(args.source), name=args.name)
    out = write_deck(deck, args.out)
    print(f"已导出到 {out}：{len(deck.sections)} 个子牌组 / {deck.card_count} 张卡片")
    for section, cards in deck.sections.items():
        print(f"  · {section}: {len(cards)} 张")
    return 0


def cmd_preview(args) -> int:
    spec = load_spec(args.deck, args.name)
    preview = build_preview(spec, args.out, pdf=args.pdf)
    print(f"预览：{preview}（{preview.stat().st_size / 1048576:.1f} MB，"
          f"{spec.card_count} 张卡片）")
    return 0


def cmd_verify(args) -> int:
    result = verify(args.apkg)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=1))
    else:
        print(f"{result['apkg']}（{result['size_bytes'] / 1048576:.1f} MB）")
        print(f"  notes={result['notes']} cards={result['cards']} decks={result['decks']} "
              f"media={result['media_entries']} 图片引用={result['img_refs_total']}")
        for name, count in result["per_deck_cards"].items():
            print(f"  · {name}: {count} 张卡")
        for warning in result["warnings"]:
            print(f"  ⚠ {warning}")
        for error in result["errors"]:
            print(f"  ✗ {error}")
        print("结构检查通过" if not result["errors"] else f"结构检查失败：{len(result['errors'])} 个错误")
    return 0 if not result["errors"] else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ankicards", description="Anki 卡组构建与校验工具")
    sub = parser.add_subparsers(dest="command", required=True)

    p_check = sub.add_parser("check", help="只校验卡片数据（不需要 genanki）")
    p_check.add_argument("deck", help="牌组目录（含 cards/*.json）")
    p_check.add_argument("--pdf", help="源 PDF，用于页码上界与裁图越界检查")
    p_check.add_argument("--name", help="覆盖顶层牌组名")
    p_check.set_defaults(func=cmd_check)

    p_build = sub.add_parser("build", help="构建 .apkg")
    p_build.add_argument("deck")
    p_build.add_argument("--out", required=True, help="输出 .apkg 路径")
    p_build.add_argument("--pdf", help="源 PDF；有图片题时必须提供")
    p_build.add_argument("--lite", action="store_true", help="不生成原文页截图")
    p_build.add_argument("--name", help="覆盖顶层牌组名")
    p_build.add_argument("--preview", help="同时输出单文件 HTML 预览")
    p_build.set_defaults(func=cmd_build)

    p_import = sub.add_parser("import", help="把 MD/TXT 源解析成 cards/*.json")
    p_import.add_argument("source", nargs="?", help="源目录或文件")
    p_import.add_argument("--adapter", help="适配器名，见 --list")
    p_import.add_argument("--out", help="输出牌组目录")
    p_import.add_argument("--name", help="覆盖顶层牌组名")
    p_import.add_argument("--list", action="store_true", help="列出可用适配器")
    p_import.set_defaults(func=cmd_import)

    p_preview = sub.add_parser("preview", help="只生成单文件 HTML 预览")
    p_preview.add_argument("deck")
    p_preview.add_argument("--out", required=True, help="输出 .html 路径")
    p_preview.add_argument("--pdf", help="源 PDF（决定能否显示原文截图与裁图）")
    p_preview.add_argument("--name", help="覆盖顶层牌组名")
    p_preview.set_defaults(func=cmd_preview)

    p_verify = sub.add_parser("verify", help="导出后结构审计（不需要源数据）")
    p_verify.add_argument("apkg")
    p_verify.add_argument("--json", action="store_true", help="输出 JSON")
    p_verify.set_defaults(func=cmd_verify)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
