"""命令行入口：ingest / import / check / build / preview / verify。

    python3 -m ankicards ingest  <手册.pdf> [--out x.json] [--allow-repaired]
    python3 -m ankicards import  <源目录> --adapter <名字> --out <牌组目录>
    python3 -m ankicards check   <牌组> [--pdf 手册.pdf] [--ingest x.json]
    python3 -m ankicards build   <牌组> --out x.apkg [--pdf 手册.pdf] [--ingest x.json]
    python3 -m ankicards preview <牌组> --out x.html [--pdf 手册.pdf] [--ingest x.json]
    python3 -m ankicards verify  <x.apkg>

退出码：0 成功；1 数据校验失败；2 用法或环境错误（缺参、文件不可读、加密 PDF 等）。
"""

from __future__ import annotations

import argparse
import json
import sys
import zipfile
from pathlib import Path

from .build import build
from .errors import CardError
from .ingest import DEFAULT_MAX_PAGES, load_ingest, main_cli as ingest_cli
from .preview import build_preview
from .schema import SOURCE_KINDS, DeckSpec, load_spec, validate
from .verify import verify


def _load_spec(args) -> DeckSpec:
    """load_spec 自己会抛 CardError（坏 JSON / 缺目录 / 缺 cards）。"""
    return load_spec(args.deck, args.name)


def _pdf_info(pdf: str | None):
    if not pdf:
        return None, None
    try:
        import pymupdf  # type: ignore
    except ImportError as exc:
        raise CardError("需要 PyMuPDF：pip install -r requirements-render.txt") from exc
    try:
        doc = pymupdf.open(pdf)
    except Exception as exc:  # noqa: BLE001 - 损坏或非 PDF
        raise CardError(f"无法打开 PDF {pdf}: {exc}") from exc
    try:
        if getattr(doc, "needs_pass", 0):
            raise CardError(f"PDF 已加密，请先解密后再使用: {pdf}")
        return doc.page_count, (doc[0].rect.width, doc[0].rect.height)
    finally:
        doc.close()


def _ingest_pages(args) -> dict[int, str] | None:
    if not getattr(args, "ingest", None):
        return None
    return load_ingest(args.ingest)


def _print_report(report) -> None:
    for warning in report.warnings:
        print(f"  ⚠ {warning}")
    for error in report.errors:
        print(f"  ✗ {error}")


def _validated(args, *, gate: bool = True):
    """check/build/preview 共用的校验链：PDF 预检 → ingest → 闸门 → validate。

    gate=True 时，含 pages 的牌组没有 ingest 直接抛 CardError(code=1)（闸门失败）。
    """
    spec = _load_spec(args)
    page_count, page_size = _pdf_info(args.pdf)
    ingest = _ingest_pages(args)
    if gate and spec.has_pages and ingest is None:
        raise CardError(
            "该牌组引用 PDF 页码，请先 ingest 并传 --ingest（交付前必须过溯源闸门）", code=1)
    report = validate(spec, page_count=page_count, page_size=page_size, ingest=ingest)
    return spec, report


def cmd_check(args) -> int:
    spec, report = _validated(args, gate=False)
    print(f"牌组 {spec.name}：{len(spec.sections)} 个子牌组 / {spec.card_count} 张卡片")
    _print_report(report)
    print("校验通过" if report.ok else f"校验失败：{len(report.errors)} 个错误")
    return 0 if report.ok else 1


def cmd_build(args) -> int:
    spec, report = _validated(args)
    _print_report(report)
    if not report.ok:
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
    if not args.source:
        raise CardError("缺少源目录/文件（或使用 --list 查看适配器）")
    if not args.adapter:
        raise CardError(f"请指定 --adapter；可用：{', '.join(sorted(ADAPTERS))}")
    if not args.out:
        raise CardError("缺少 --out（输出牌组目录）")
    func = ADAPTERS.get(args.adapter)
    if func is None:
        raise CardError(f"未知 adapter: {args.adapter}；可用：{', '.join(sorted(ADAPTERS))}")
    deck = func(Path(args.source)) if not args.name else func(Path(args.source), name=args.name)
    if args.source_kind:
        deck.source_kind = args.source_kind
    out = write_deck(deck, args.out, force=args.force)
    print(f"已导出到 {out}：{len(deck.sections)} 个子牌组 / {deck.card_count} 张卡片 "
          f"/ source_kind={deck.source_kind}")
    for section, cards in deck.sections.items():
        print(f"  · {section}: {len(cards)} 张")
    return 0


def cmd_ingest(args) -> int:
    return ingest_cli(args)


def cmd_preview(args) -> int:
    spec, report = _validated(args)
    _print_report(report)
    if not report.ok:
        print("预览中止：先修数据")
        return 1
    preview = build_preview(spec, args.out, pdf=args.pdf)
    print(f"预览：{preview}（{preview.stat().st_size / 1048576:.1f} MB，"
          f"{spec.card_count} 张卡片）")
    return 0


def cmd_verify(args) -> int:
    try:
        result = verify(args.apkg)
    except (OSError, zipfile.BadZipFile) as exc:
        raise CardError(f"无法读取 apkg {args.apkg}: {exc}") from exc
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
    p_check.add_argument("--ingest", help="ingest 产物 JSON；启用溯源闸门（页码必须存在且有文本）")
    p_check.add_argument("--name", help="覆盖顶层牌组名")
    p_check.set_defaults(func=cmd_check)

    p_build = sub.add_parser("build", help="构建 .apkg")
    p_build.add_argument("deck")
    p_build.add_argument("--out", required=True, help="输出 .apkg 路径")
    p_build.add_argument("--pdf", help="源 PDF；有图片题时必须提供")
    p_build.add_argument("--ingest", help="ingest 产物；引用 PDF 页码的牌组必须提供")
    p_build.add_argument("--lite", action="store_true", help="不生成原文页截图")
    p_build.add_argument("--name", help="覆盖顶层牌组名")
    p_build.add_argument("--preview", help="同时输出单文件 HTML 预览")
    p_build.set_defaults(func=cmd_build)

    p_import = sub.add_parser("import", help="把 MD/TXT 源解析成 cards/*.json")
    p_import.add_argument("source", nargs="?", help="源目录或文件")
    p_import.add_argument("--adapter", help="适配器名，见 --list")
    p_import.add_argument("--out", help="输出牌组目录")
    p_import.add_argument("--name", help="覆盖顶层牌组名")
    p_import.add_argument("--source-kind", choices=sorted(SOURCE_KINDS - {"unknown"}),
                          help="写入 deck.json 的 source_kind（默认由适配器决定）")
    p_import.add_argument("--list", action="store_true", help="列出可用适配器")
    p_import.add_argument("--force", action="store_true", help="目标目录已有卡片时也强制覆盖")
    p_import.set_defaults(func=cmd_import)

    p_ingest = sub.add_parser("ingest", help="把文本型 PDF 摄取成逐页文本 JSON")
    p_ingest.add_argument("source", help="PDF 文件（DOCX/MD/TXT 会被明确拒绝）")
    p_ingest.add_argument("--out", help="输出 JSON；默认 .work/ingest/<名字>-<sha8>.json")
    p_ingest.add_argument("--max-pages", type=int, default=DEFAULT_MAX_PAGES,
                          help=f"页数上限（默认 {DEFAULT_MAX_PAGES}）")
    p_ingest.add_argument("--allow-repaired", action="store_true",
                          help="接受被引擎修复过的损坏 PDF（默认拒绝）")
    p_ingest.set_defaults(func=cmd_ingest)

    p_preview = sub.add_parser("preview", help="只生成单文件 HTML 预览")
    p_preview.add_argument("deck")
    p_preview.add_argument("--out", required=True, help="输出 .html 路径")
    p_preview.add_argument("--pdf", help="源 PDF（决定能否显示原文截图与裁图）")
    p_preview.add_argument("--ingest", help="ingest 产物；引用 PDF 页码的牌组必须提供")
    p_preview.add_argument("--name", help="覆盖顶层牌组名")
    p_preview.set_defaults(func=cmd_preview)

    p_verify = sub.add_parser("verify", help="导出后结构审计（不需要源数据）")
    p_verify.add_argument("apkg")
    p_verify.add_argument("--json", action="store_true", help="输出 JSON")
    p_verify.set_defaults(func=cmd_verify)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except CardError as exc:
        print(f"✗ {exc}", file=sys.stderr)
        return exc.code


if __name__ == "__main__":
    sys.exit(main())
