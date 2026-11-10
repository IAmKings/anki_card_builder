"""命令行入口：ingest / import / check / build / preview / verify。

    python3 -m ankicards ingest  <手册.pdf> [--out x.json] [--allow-repaired]
    python3 -m ankicards import  <源目录> --adapter <名字> --out <牌组目录> [--strict]
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
from .errors import CardError, GateError
from .ingest import (DEFAULT_MAX_BLOCKS, DEFAULT_MAX_LINES, DEFAULT_MAX_PAGES,
                     DEFAULT_TXT_ENCODING, file_sha256, load_ingest,
                     main_cli as ingest_cli)
from .preview import build_preview
from .schema import SOURCE_KINDS, DeckSpec, load_json, load_spec, validate
from .verify import verify


def _load_spec(args) -> DeckSpec:
    """load_spec 自己会抛 CardError（坏 JSON / 缺目录 / 缺 cards）。"""
    return load_spec(args.deck, args.name)


def _pdf_info(pdf: str | None, pages: set[int] | None = None):
    """返回 (page_count, page_sizes)。page_sizes 只取需要的页，避免大 PDF 全量读尺寸。"""
    if not pdf:
        return None, {}
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
        wanted = {p for p in (pages or set()) if isinstance(p, int) and 1 <= p <= doc.page_count}
        sizes = {p: (doc[p - 1].rect.width, doc[p - 1].rect.height) for p in sorted(wanted)}
        return doc.page_count, sizes
    finally:
        doc.close()


def _docx_info(docx: str | None) -> None:
    """--docx 的源文件预检；路径不存在、是目录或不可读都算用法错误（exit 2）。"""
    if not docx:
        return
    path = Path(docx)
    if not path.exists():
        raise CardError(f"找不到 DOCX: {path}")
    if not path.is_file():
        raise CardError(f"不是文件: {path}")


def _txt_info(txt: str | None) -> None:
    """--txt 的源文件预检；路径不存在、是目录或不是 .txt 都算用法错误（exit 2）。"""
    if not txt:
        return
    path = Path(txt)
    if not path.exists():
        raise CardError(f"找不到 TXT: {path}")
    if not path.is_file():
        raise CardError(f"不是文件: {path}")
    if path.suffix.lower() != ".txt":
        raise CardError(f"--txt 只接受 .txt 文件: {path}")


def _web_info(html: str | None) -> None:
    """--html 的源文件预检；路径不存在、是目录或不是 .html/.htm 都算用法错误（exit 2）。"""
    if not html:
        return
    path = Path(html)
    if not path.exists():
        raise CardError(f"找不到 HTML: {path}")
    if not path.is_file():
        raise CardError(f"不是文件: {path}")
    if path.suffix.lower() not in (".html", ".htm"):
        raise CardError(f"--html 只接受 .html/.htm 文件: {path}")


def _ingest_pages(args):
    if not getattr(args, "ingest", None):
        return None
    return load_ingest(args.ingest)


def _print_report(report) -> None:
    for warning in report.warnings:
        print(f"  ⚠ {warning}")
    for error in report.errors:
        print(f"  ✗ {error}")


def _validated(args):
    """check/build/preview 共用的校验链：PDF 预检 → ingest → validate。

    只返回 (spec, report, ingest)，不在这里拦闸门——先让调用方打印报告，
    数据错误优先于闸门（避免 pages:"5" 被“请先 ingest”掩盖）。
    """
    spec = _load_spec(args)
    pdf = getattr(args, "pdf", None)
    docx = getattr(args, "docx", None)
    txt = getattr(args, "txt", None)
    html = getattr(args, "html", None)
    epub = getattr(args, "epub", None)
    sources = [name for name, value in (("--pdf", pdf), ("--docx", docx),
                                        ("--txt", txt), ("--html", html),
                                        ("--epub", epub))
               if value]
    if len(sources) > 1:
        raise CardError(f"{'、'.join(sources)} 只能给一个")
    _docx_info(docx)
    _txt_info(txt)
    _web_info(html)
    crop_pages = {c.get("page") for c in spec.crops.values() if isinstance(c.get("page"), int)}
    page_count, page_sizes = _pdf_info(pdf, crop_pages)
    ingest = _ingest_pages(args)
    if ingest and docx:
        if ingest.format != "docx":
            raise CardError("--docx 需要 DOCX 的 ingest 产物")
        if ingest.source_sha256:
            try:
                actual = file_sha256(Path(docx))
            except OSError as exc:
                raise CardError(f"无法读取 DOCX {docx}: {exc}") from exc
            if actual != ingest.source_sha256:
                raise CardError("--ingest 与 --docx 不是同一份文件（sha256 不一致）")
        else:
            print("  ⚠ ingest 缺少 source_sha256，跳过同源校验", file=sys.stderr)
    elif ingest and txt:
        if ingest.format != "txt":
            raise CardError("--txt 需要 TXT 的 ingest 产物")
        if ingest.source_sha256:
            try:
                actual = file_sha256(Path(txt))
            except OSError as exc:
                raise CardError(f"无法读取 TXT {txt}: {exc}") from exc
            if actual != ingest.source_sha256:
                raise CardError("--ingest 与 --txt 不是同一份文件（sha256 不一致）")
        else:
            print("  ⚠ ingest 缺少 source_sha256，跳过同源校验", file=sys.stderr)
    elif ingest and html:
        if ingest.format != "web":
            raise CardError("--html 需要 WEB 的 ingest 产物")
        if ingest.source_sha256:
            try:
                actual = file_sha256(Path(html))
            except OSError as exc:
                raise CardError(f"无法读取 HTML {html}: {exc}") from exc
            if actual != ingest.source_sha256:
                raise CardError("--ingest 与 --html 不是同一份文件（sha256 不一致）")
        else:
            print("  ⚠ ingest 缺少 source_sha256（URL 产物），跳过同源校验", file=sys.stderr)
    elif ingest and epub:
        if ingest.format != "epub":
            raise CardError("--epub 需要 EPUB 的 ingest 产物")
        if ingest.source_sha256:
            try:
                actual = file_sha256(Path(epub))
            except OSError as exc:
                raise CardError(f"无法读取 EPUB {epub}: {exc}") from exc
            if actual != ingest.source_sha256:
                raise CardError("--ingest 与 --epub 不是同一份文件（sha256 不一致）")
        else:
            print("  ⚠ ingest 缺少 source_sha256，跳过同源校验", file=sys.stderr)
    elif ingest and pdf:
        if ingest.format != "pdf":
            raise CardError("--pdf 需要 PDF 的 ingest 产物")
        if ingest.source_sha256:
            if file_sha256(Path(pdf)) != ingest.source_sha256:
                raise CardError("--ingest 与 --pdf 不是同一份文件（sha256 不一致）")
        else:
            print("  ⚠ ingest 缺少 source_sha256，跳过同源校验", file=sys.stderr)
    report = validate(spec, page_count=page_count, page_sizes=page_sizes,
                      ingest=ingest.pages if ingest else None,
                      locators=ingest.locators if ingest else None)
    return spec, report, ingest


def _require_gate(spec: DeckSpec, ingest) -> None:
    """含 pages 或 DOCX 定位的牌组构建/预览前必须过溯源闸门；在报告打印之后调用。"""
    needs_ingest = (spec.has_pages or spec.source_kind in ("docx", "txt", "web", "epub")
                    or spec.has_docx_locators or spec.has_txt_locators
                    or spec.has_web_locators or spec.has_epub_locators)
    if needs_ingest and ingest is None:
        raise GateError(
            "该牌组引用 PDF 页码、DOCX/TXT 或 WEB 定位，请先 ingest 并传 --ingest"
            "（交付前必须过溯源闸门）")


def cmd_check(args) -> int:
    spec, report, _ingest = _validated(args)
    print(f"牌组 {spec.name}：{len(spec.sections)} 个子牌组 / {spec.card_count} 张卡片")
    _print_report(report)
    print("校验通过" if report.ok else f"校验失败：{len(report.errors)} 个错误")
    return 0 if report.ok else 1


def _print_plan_report(report, stats: dict) -> None:
    for error in report.errors:
        print(f"✗ {error}")
    for warning in report.warnings:
        print(f"△ {warning}")
    line = f"卡片 {stats['cards']} / 未出卡 {stats['skipped']}"
    kinds = stats.get("kinds") or {}
    if kinds:
        line += " / 卡型 " + " ".join(f"{name} {count}" for name, count in sorted(kinds.items()))
    if stats.get("coverage") is not None:
        line += (f" / 覆盖率 {stats['covered']}/{stats['groups']}"
                 f"（{stats['coverage']:.0%}）")
    density = stats.get("density") or {}
    if density.get("chars_per_card") is not None:
        line += (f" / 密度 {density['chars_per_card']:.0f} 字/张"
                 f"（目标 {density['min']}–{density['max']}）")
    print(line)


def _add_density_args(parser) -> None:
    """--density 的三种口径与显式上下限；默认不启用。"""
    parser.add_argument("--density", choices=["manual", "novel", "essay"], default=None,
                        help="按口径检查密度与卡型配额（只提示，不拦编译）")
    parser.add_argument("--density-min", type=int, default=None,
                        help="覆盖密度下限（字/张）")
    parser.add_argument("--density-max", type=int, default=None,
                        help="覆盖密度上限（字/张）")


def cmd_plan_check(args) -> int:
    from .ingest import load_ingest
    from .plan import check_plan, load_plan

    report, stats = check_plan(load_plan(args.plan), load_ingest(args.ingest),
                               min_coverage=args.min_coverage,
                               profile=args.profile,
                               density=args.density,
                               density_min=args.density_min,
                               density_max=args.density_max)
    _print_plan_report(report, stats)
    if report.ok:
        print("校验通过")
        return 0
    return 1


def cmd_plan_compile(args) -> int:
    from .ingest import load_ingest
    from .plan import compile_plan, load_plan

    report, stats, out = compile_plan(load_plan(args.plan), load_ingest(args.ingest),
                                      args.out, force=args.force,
                                      min_coverage=args.min_coverage,
                                      with_key=args.with_key,
                                      profile=args.profile,
                                      density=args.density,
                                      density_min=args.density_min,
                                      density_max=args.density_max)
    _print_plan_report(report, stats)
    if out is None:
        print("✗ 有错误，未写牌组")
        return 1
    print(f"已编译到 {out}")
    return 0


def cmd_plan_diff(args) -> int:
    from .plan import diff_plan, load_plan

    result = diff_plan(load_plan(args.plan), args.deck)
    print(f"plan {result['planned']} 张 / 现有牌组 {result['existing']} 张")
    for item in result["added"]:
        print(f"  + [{item['locator']}] {item['text']}")
    for item in result["removed"]:
        print(f"  - [{item['locator']}] {item['text']}")
    for item in result["changed"]:
        print(f"  ~ [{item['locator']}] {item['was']} → {item['now']}")
    if not (result["added"] or result["removed"] or result["changed"]):
        print("无变化")
    return 0


def cmd_build(args) -> int:
    spec, report, ingest = _validated(args)
    _print_report(report)
    if not report.ok:
        print("构建中止：先修数据")
        return 1
    _require_gate(spec, ingest)
    stats = build(spec, args.out, pdf=args.pdf, lite=args.lite)
    print(json.dumps(stats, ensure_ascii=False, indent=1))
    if args.preview:
        preview = build_preview(spec, args.preview, pdf=args.pdf)
        print(f"预览：{preview}（{preview.stat().st_size / 1048576:.1f} MB）")
    return 0


def _print_import_health(deck) -> None:
    """打印内容层检查与未出卡账本；import-report.json 里是同一份数据的全量。"""
    if deck.findings:
        levels: dict[str, int] = {}
        for item in deck.findings:
            levels[item["level"]] = levels.get(item["level"], 0) + 1
        print(f"  内容检查：{len(deck.findings)} 个可疑项"
              f"（error {levels.get('error', 0)} / warning {levels.get('warning', 0)}）")
        for item in deck.findings[:10]:
            mark = "✗" if item["level"] == "error" else "⚠"
            print(f"    {mark} {item['rule']} [{item['locator']}] {item['message']}")
        if len(deck.findings) > 10:
            print(f"    … 另 {len(deck.findings) - 10} 条见 import-report.json")
    if deck.skipped:
        parts = " / ".join(f"{reason} {count}"
                           for reason, count in sorted(deck.count_skipped().items()))
        print(f"  未出卡 {len(deck.skipped)} 处（{parts}）")


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
    kwargs: dict = {} if not args.name else {"name": args.name}
    if getattr(args, "ingest", None):
        allowed = ("docx-points", "txt-points", "web-points")
        if args.adapter not in allowed:
            raise CardError(
                f"--ingest 只支持 {', '.join(allowed)}，当前为 {args.adapter}")
        manifest = load_json(Path(args.ingest))
        if not isinstance(manifest, dict):
            raise CardError(f"{args.ingest}: 不是有效的 ingest 产物（顶层必须是对象）")
        sha = manifest.get("source_sha256")
        source_path = Path(args.source)
        if isinstance(sha, str) and source_path.is_file() and source_path.suffix.lower() != ".json":
            if file_sha256(source_path) != sha:
                raise CardError(
                    "--ingest 与源文件不匹配（sha256 不一致）：确认用的是同一份文件，"
                    "或重新跑 ingest")
        kwargs["ingest"] = manifest
    deck = func(Path(args.source), **kwargs)
    if args.source_kind:
        deck.source_kind = args.source_kind
    errors = [item for item in deck.findings if item["level"] == "error"]
    if getattr(args, "strict", False) and errors:
        _print_import_health(deck)
        print(f"✗ --strict：{len(errors)} 个错误级内容问题，未写牌组")
        return 1
    out = write_deck(deck, args.out, force=args.force)
    print(f"已导出到 {out}：{len(deck.sections)} 个子牌组 / {deck.card_count} 张卡片 "
          f"/ source_kind={deck.source_kind}")
    for warning in deck.warnings:
        print(f"  ⚠ {warning}")
    for section, cards in deck.sections.items():
        print(f"  · {section}: {len(cards)} 张")
    _print_import_health(deck)
    return 0


def cmd_ingest(args) -> int:
    return ingest_cli(args)


def cmd_preview(args) -> int:
    spec, report, ingest = _validated(args)
    _print_report(report)
    if not report.ok:
        print("预览中止：先修数据")
        return 1
    _require_gate(spec, ingest)
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
    p_check.add_argument("--docx", help="源 DOCX，用于与 ingest 的同源校验")
    p_check.add_argument("--txt", help="源 TXT，用于与 ingest 的同源校验")
    p_check.add_argument("--epub", help="源 EPUB；与 --ingest 做同源校验")
    p_check.add_argument("--html", help="本地 HTML，用于与 ingest 的同源校验")
    p_check.add_argument("--ingest", help="ingest 产物 JSON；启用溯源闸门（页码/定位必须存在且有文本）")
    p_check.add_argument("--name", help="覆盖顶层牌组名")
    p_check.set_defaults(func=cmd_check)

    p_build = sub.add_parser("build", help="构建 .apkg")
    p_build.add_argument("deck")
    p_build.add_argument("--out", required=True, help="输出 .apkg 路径")
    p_build.add_argument("--pdf", help="源 PDF；有图片题时必须提供")
    p_build.add_argument("--docx", help="源 DOCX；与 --ingest 做同源校验")
    p_build.add_argument("--txt", help="源 TXT；与 --ingest 做同源校验")
    p_build.add_argument("--epub", help="源 EPUB；与 --ingest 做同源校验")
    p_build.add_argument("--html", help="本地 HTML；与 --ingest 做同源校验")
    p_build.add_argument("--ingest", help="ingest 产物；引用 PDF 页码/DOCX 定位的牌组必须提供")
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
    p_import.add_argument("--ingest", metavar="JSON",
                          help="ingest 产物；按 groups 合并续行/子项，source 写区间")
    p_import.add_argument("--force", action="store_true", help="目标目录已有卡片时也强制覆盖")
    p_import.add_argument("--strict", action="store_true",
                          help="error 级内容问题视为失败（退出码 1，且不写牌组）")
    p_import.set_defaults(func=cmd_import)

    p_plan = sub.add_parser("plan", help="校验/编译/对比 plan.json（每张卡都要有原文引用）")
    plan_sub = p_plan.add_subparsers(dest="plan_command", required=True)

    p_plan_check = plan_sub.add_parser("check", help="校验引用锚定、理由枚举与覆盖率")
    p_plan_check.add_argument("plan", help="plan.json 路径")
    p_plan_check.add_argument("--ingest", required=True, help="ingest 产物 JSON")
    p_plan_check.add_argument("--profile", choices=["manual", "novel", "essay"], default=None,
                              help="内容形态；novel 放宽引用长度与未出卡理由")
    p_plan_check.add_argument("--min-coverage", type=float, default=None,
                              help="分组覆盖率阈值（0–1），低于即失败")
    _add_density_args(p_plan_check)
    p_plan_check.set_defaults(func=cmd_plan_check)

    p_plan_compile = plan_sub.add_parser("compile", help="校验通过后写出牌组目录")
    p_plan_compile.add_argument("plan", help="plan.json 路径")
    p_plan_compile.add_argument("--out", required=True, help="输出牌组目录")
    p_plan_compile.add_argument("--ingest", required=True, help="ingest 产物 JSON")
    p_plan_compile.add_argument("--profile", choices=["manual", "novel", "essay"], default=None,
                                help="内容形态；novel 放宽引用长度与未出卡理由")
    p_plan_compile.add_argument("--min-coverage", type=float, default=None,
                                help="分组覆盖率阈值（0–1），低于即失败")
    _add_density_args(p_plan_compile)
    p_plan_compile.add_argument("--force", action="store_true",
                                help="目标目录已有卡片时也强制覆盖")
    p_plan_compile.add_argument("--with-key", action="store_true",
                                help="给每张卡生成稳定身份 key（只用于新牌组）")
    p_plan_compile.set_defaults(func=cmd_plan_compile)

    p_plan_diff = plan_sub.add_parser("diff", help="对比 plan 与已写出的牌组会变哪些卡")
    p_plan_diff.add_argument("plan", help="plan.json 路径")
    p_plan_diff.add_argument("--deck", required=True, help="已写出的牌组目录")
    p_plan_diff.set_defaults(func=cmd_plan_diff)

    p_ingest = sub.add_parser("ingest", help="把 PDF/DOCX/TXT 摄取成可寻址的文本 JSON")
    p_ingest.add_argument("source", help="PDF/DOCX/TXT 文件（MD 请用 import --adapter）")
    p_ingest.add_argument("--out", help="输出 JSON；默认 .work/ingest/<名字>-<sha8>.json")
    p_ingest.add_argument("--max-pages", type=int, default=DEFAULT_MAX_PAGES,
                          help=f"PDF 页数上限（默认 {DEFAULT_MAX_PAGES}）")
    p_ingest.add_argument("--max-blocks", type=int, default=DEFAULT_MAX_BLOCKS,
                          help=f"DOCX 块数上限（默认 {DEFAULT_MAX_BLOCKS}）")
    p_ingest.add_argument("--max-lines", type=int, default=DEFAULT_MAX_LINES,
                          help=f"TXT 行数上限（默认 {DEFAULT_MAX_LINES}）")
    p_ingest.add_argument("--encoding", default=DEFAULT_TXT_ENCODING,
                          help=f"TXT 编码（默认 {DEFAULT_TXT_ENCODING}）")
    p_ingest.add_argument("--max-bytes", type=int, default=None,
                          help="HTML 文件/URL 响应体大小上限（字节；默认 5 MB）")
    p_ingest.add_argument("--timeout", type=float, default=20,
                          help="URL 抓取超时秒数（默认 20）")
    p_ingest.add_argument("--allow-private-network", action="store_true",
                          help="允许抓取 localhost/内网 URL（默认拒绝）")
    p_ingest.add_argument("--allow-repaired", action="store_true",
                          help="接受被引擎修复过的损坏 PDF（默认拒绝）")
    p_ingest.set_defaults(func=cmd_ingest)

    p_preview = sub.add_parser("preview", help="只生成单文件 HTML 预览")
    p_preview.add_argument("deck")
    p_preview.add_argument("--out", required=True, help="输出 .html 路径")
    p_preview.add_argument("--pdf", help="源 PDF（决定能否显示原文截图与裁图）")
    p_preview.add_argument("--docx", help="源 DOCX；与 --ingest 做同源校验")
    p_preview.add_argument("--txt", help="源 TXT；与 --ingest 做同源校验")
    p_preview.add_argument("--epub", help="源 EPUB；与 --ingest 做同源校验")
    p_preview.add_argument("--html", help="本地 HTML；与 --ingest 做同源校验")
    p_preview.add_argument("--ingest", help="ingest 产物；引用 PDF 页码/DOCX 定位的牌组必须提供")
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
