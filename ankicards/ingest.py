"""文本摄取：PDF 逐页、DOCX 逐段/逐表格行，产出可寻址的 JSON 清单。

首版范围（已与用户确认）：
- PDF：只支持文本型；扫描件/加密/损坏明确拒绝，不做 OCR。
- DOCX：body 顺序的段落（para:N）与表格行（table:T/rR）；忽略页眉页脚/图片/批注。
- MD/TXT 请走 `import --adapter`。
- 输出固定写到 .work/ingest/（被 .gitignore 忽略），并带源文件 sha256。
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from .docx import iter_docx_blocks
from .errors import CardError
from .schema import load_json

DEFAULT_MAX_PAGES = 2000
DEFAULT_MAX_BLOCKS = 5000
MAX_DOCX_BYTES = 20 * 1024 * 1024
MAX_DOCX_UNCOMPRESSED_BYTES = 200 * 1024 * 1024
EMPTY_PAGE_RATIO_LIMIT = 0.2   # 超过即给 warning
EMPTY_FAIL_RATIO = 0.5         # 达到即拒绝


@dataclass
class IngestData:
    """load_ingest 的返回值：页码/定位→文本 + 源文件 sha256（可能缺省）。"""

    pages: dict[int, str]
    source_sha256: str | None = None
    format: str = "pdf"
    locators: dict[str, str] = field(default_factory=dict)


@dataclass
class IngestResult:
    """摄取结果：manifest 是落盘内容，out_path 是实际写入位置。"""

    manifest: dict
    out_path: Path


class IngestError(CardError):
    """摄取失败；沿用 CardError 的退出码语义（2 = 输入/环境问题）。"""


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _require_pdf(path: Path) -> None:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return
    raise IngestError(
        f"{suffix or '(无扩展名)'} 不是 PDF；请用 `python3 -m ankicards ingest <文件>` "
        "按格式分派，或 `import --adapter`。")


def _import_docx():
    try:
        import docx  # type: ignore
    except ImportError as exc:  # pragma: no cover - 依赖环境
        raise IngestError("需要 python-docx：pip install -r requirements.txt") from exc
    return docx


def _check_docx_zip(path: Path) -> None:
    """DOCX 是 zip；限制解压后总大小，避免很小的压缩包膨胀成超大 XML。"""
    try:
        with zipfile.ZipFile(path) as archive:
            total = sum(info.file_size for info in archive.infolist())
    except zipfile.BadZipFile as exc:
        raise IngestError(f"无法打开 DOCX（损坏或已加密）: {exc}") from exc
    except OSError as exc:
        raise IngestError(f"无法读取 DOCX: {exc}") from exc
    if total > MAX_DOCX_UNCOMPRESSED_BYTES:
        raise IngestError(
            f"DOCX 解压后约 {total // (1024 * 1024)} MB，超过 "
            f"{MAX_DOCX_UNCOMPRESSED_BYTES // (1024 * 1024)} MB 上限；请拆分文档。")


def _default_out(path: Path, sha: str) -> Path:
    stem = re.sub(r"[^\w\-]+", "_", path.stem)[:40] or "doc"
    return Path.cwd() / ".work" / "ingest" / f"{stem}-{sha[:8]}.json"


def _check_out_path(out: Path, repo_root: Path | None = None) -> None:
    """只按「相对仓库根」判断，避免仓库恰好位于 output/ 或 cards/ 目录下时被误拒。"""
    root = (repo_root or Path(__file__).resolve().parents[1]).resolve()
    try:
        rel = out.resolve().relative_to(root)
    except ValueError:
        return  # 仓库外，不限制
    if rel.parts[:1] == ("output",) or "cards" in rel.parts:
        raise IngestError(f"拒绝写入 {out}：ingest 产物请留在 .work/，不要放进 output/ 或 cards/")


def ingest_pdf(pdf_path: str | Path, out: str | Path | None = None,
               max_pages: int = DEFAULT_MAX_PAGES,
               allow_repaired: bool = False,
               repo_root: Path | None = None) -> IngestResult:
    path = Path(pdf_path).expanduser().resolve()
    if not path.exists():
        raise IngestError(f"找不到文件: {path}")
    if not path.is_file():
        raise IngestError(f"不是文件: {path}")
    _require_pdf(path)

    try:
        import pymupdf  # type: ignore
    except ImportError as exc:  # pragma: no cover - 依赖环境
        raise IngestError(
            "需要 PyMuPDF 才能摄取 PDF：pip install -r requirements-render.txt") from exc

    sha = file_sha256(path)
    out_path = Path(out).expanduser() if out else _default_out(path, sha)
    _check_out_path(out_path, repo_root)

    try:
        doc = pymupdf.open(str(path))
    except Exception as exc:  # noqa: BLE001 - 损坏/非 PDF 字节
        raise IngestError(f"无法打开 PDF（文件损坏或不是 PDF）: {exc}") from exc

    try:
        if getattr(doc, "needs_pass", 0):
            raise IngestError("PDF 已加密：请先解密（如 qpdf --decrypt）后再摄取。")
        page_count = doc.page_count
        if page_count <= 0:
            raise IngestError("PDF 没有页面")
        if page_count > max_pages:
            raise IngestError(
                f"PDF 有 {page_count} 页，超过上限 {max_pages}；"
                "请拆分文件或用 --max-pages 显式放宽。")
        repaired = bool(getattr(doc, "is_repaired", False))
        if repaired and not allow_repaired:
            raise IngestError(
                "PDF 结构损坏（已被引擎自动修复），文本可能缺失。"
                "确认接受请加 --allow-repaired 重跑。")

        units = []
        empty_pages = []
        for index, page in enumerate(doc, 1):
            text = page.get_text("text")
            if not text.strip():
                empty_pages.append(index)
            units.append({
                "id": f"page:{index}",
                "page": index,
                "chars": len(text.strip()),
                "text": text,
            })
    finally:
        doc.close()

    total_chars = sum(unit["chars"] for unit in units)
    empty_ratio = len(empty_pages) / len(units)
    warnings: list[str] = []
    if total_chars == 0:
        raise IngestError(
            "未提取到任何文本：这是扫描版/纯图片 PDF，本工具没有 OCR，无法转成卡片。")
    if empty_ratio >= EMPTY_FAIL_RATIO:
        raise IngestError(
            f"{len(empty_pages)}/{len(units)} 页没有文本"
            f"（≥{int(EMPTY_FAIL_RATIO * 100)}%），疑似扫描件或排版异常页："
            f"空页 = {empty_pages[:20]}{'…' if len(empty_pages) > 20 else ''}")
    if empty_ratio >= EMPTY_PAGE_RATIO_LIMIT:
        warnings.append(
            f"{len(empty_pages)}/{len(units)} 页没有文本（>{int(EMPTY_PAGE_RATIO_LIMIT * 100)}%）；"
            "引用这些页的卡片会被 check --ingest 拦下")
    if repaired:
        warnings.append("PDF 曾被引擎修复（is_repaired），文本可能有缺失，请抽查")

    manifest = {
        "format": "pdf",
        "source": path.name,
        "source_sha256": sha,
        "unit_kind": "page",
        "unit_count": len(units),
        "total_chars": total_chars,
        "empty_pages": empty_pages,
        "repaired": repaired,
        "warnings": warnings,
        "engine": f"pymupdf {pymupdf.__version__}",
        "units": units,
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(manifest, ensure_ascii=False, indent=1, sort_keys=True) + "\n"
    out_path.write_text(payload, encoding="utf-8")
    return IngestResult(manifest=manifest, out_path=out_path)


def ingest_docx(docx_path: str | Path, out: str | Path | None = None,
                max_blocks: int = DEFAULT_MAX_BLOCKS,
                repo_root: Path | None = None) -> IngestResult:
    """把 .docx 抽成 body 顺序的段落/表格行清单。"""
    path = Path(docx_path).expanduser().resolve()
    if not path.exists():
        raise IngestError(f"找不到文件: {path}")
    if not path.is_file():
        raise IngestError(f"不是文件: {path}")
    suffix = path.suffix.lower()
    if suffix != ".docx":
        raise IngestError(f"只支持 .docx；{suffix or '(无扩展名)'} 请先另存为 .docx")
    if path.stat().st_size > MAX_DOCX_BYTES:
        raise IngestError(
            f"DOCX 超过 {MAX_DOCX_BYTES // (1024 * 1024)} MB 上限；请拆分文档。")
    _check_docx_zip(path)

    sha = file_sha256(path)
    out_path = Path(out).expanduser() if out else _default_out(path, sha)
    _check_out_path(out_path, repo_root)

    docx = _import_docx()
    try:
        doc = docx.Document(str(path))
    except Exception as exc:  # noqa: BLE001 - 损坏/加密的异常类型不稳定
        raise IngestError(f"无法打开 DOCX（损坏或已加密）: {exc}") from exc

    units = []
    empty_units = []
    for block in iter_docx_blocks(doc):
        if len(units) >= max_blocks:
            raise IngestError(
                f"块数超过上限 {max_blocks}；请拆分文档或用 --max-blocks 放宽。")
        if not block.text.strip():
            empty_units.append(block.locator)
        units.append({
            "id": block.locator,
            "locator": block.locator,
            "kind": block.kind,
            "chars": len(block.text.strip()),
            "text": block.text,
        })

    total_chars = sum(unit["chars"] for unit in units)
    empty_ratio = len(empty_units) / len(units) if units else 0.0
    warnings: list[str] = []
    if total_chars == 0:
        raise IngestError(
            "没有可提取文本：DOCX 里没有段落/表格文本（本工具不含 OCR/图片）。")
    if empty_ratio >= EMPTY_FAIL_RATIO:
        raise IngestError(
            f"{len(empty_units)}/{len(units)} 块没有文本"
            f"（≥{int(EMPTY_FAIL_RATIO * 100)}%），疑似空白页/图片文档。")
    if empty_ratio >= EMPTY_PAGE_RATIO_LIMIT:
        warnings.append(
            f"{len(empty_units)}/{len(units)} 块没有文本"
            f"（>{int(EMPTY_PAGE_RATIO_LIMIT * 100)}%）；引用这些块的卡片会被闸门拦下")

    manifest = {
        "format": "docx",
        "source": path.name,
        "source_sha256": sha,
        "unit_kind": "block",
        "unit_count": len(units),
        "total_chars": total_chars,
        "empty_units": empty_units,
        "warnings": warnings,
        "engine": f"python-docx {docx.__version__}",
        "units": units,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(manifest, ensure_ascii=False, indent=1, sort_keys=True) + "\n"
    out_path.write_text(payload, encoding="utf-8")
    return IngestResult(manifest=manifest, out_path=out_path)


def ingest(source: str | Path, out: str | Path | None = None,
           max_pages: int = DEFAULT_MAX_PAGES,
           max_blocks: int = DEFAULT_MAX_BLOCKS,
           allow_repaired: bool = False,
           repo_root: Path | None = None) -> IngestResult:
    """按扩展名分派：.pdf → ingest_pdf，.docx → ingest_docx。"""
    path = Path(source).expanduser().resolve()
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return ingest_pdf(path, out=out, max_pages=max_pages,
                          allow_repaired=allow_repaired, repo_root=repo_root)
    if suffix == ".docx":
        return ingest_docx(path, out=out, max_blocks=max_blocks, repo_root=repo_root)
    if suffix in (".doc", ".docm"):
        raise IngestError(f"只支持 .docx；{suffix} 请先另存为 .docx")
    if suffix in (".md", ".markdown", ".txt"):
        raise IngestError(f"{suffix} 不是 PDF/DOCX；请用 `python3 -m ankicards import --adapter`。")
    raise IngestError(f"不支持的文件类型: {suffix or '(无扩展名)'}")


def load_ingest(path: str | Path) -> IngestData:
    """读 ingest 产物，返回页码/定位文本与源文件 sha256，供溯源闸门使用。"""
    try:
        data = load_json(Path(path))
    except CardError as exc:
        raise IngestError(str(exc)) from exc
    if not isinstance(data, dict):
        raise IngestError(f"{path} 不是有效的 ingest 产物（顶层必须是对象）")
    units = data.get("units")
    if not isinstance(units, list):
        raise IngestError(f"{path} 不是有效的 ingest 产物（缺少 units）")
    sha = data.get("source_sha256")
    if sha is not None and not isinstance(sha, str):
        raise IngestError(f"{path}: source_sha256 必须是字符串")
    fmt = data.get("format")
    if fmt not in (None, "pdf", "docx"):
        raise IngestError(f"{path}: format 必须是 pdf/docx，实际为 {fmt!r}")
    if fmt is None:
        first = units[0] if units else None
        fmt = "docx" if isinstance(first, dict) and "locator" in first else "pdf"

    if fmt == "docx":
        locators: dict[str, str] = {}
        for unit in units:
            if not isinstance(unit, dict):
                raise IngestError(f"{path}: units 必须是对象数组")
            locator = unit.get("locator") or unit.get("id")
            if not isinstance(locator, str) or not locator:
                raise IngestError(f"{path}: DOCX unit 缺少 locator")
            if locator in locators:
                raise IngestError(f"{path}: DOCX locator 重复: {locator}")
            locators[locator] = str(unit.get("text", ""))
        if not locators:
            raise IngestError(f"{path} 里没有任何段落/表格行")
        return IngestData(pages={}, source_sha256=sha, format="docx", locators=locators)

    pages: dict[int, str] = {}
    for unit in units:
        if not isinstance(unit, dict) or not isinstance(unit.get("page"), int):
            raise IngestError(f"{path}: units 必须是含整数 page 的对象数组")
        pages[unit["page"]] = str(unit.get("text", ""))
    if not pages:
        raise IngestError(f"{path} 里没有任何页面")
    return IngestData(pages=pages, source_sha256=sha, format="pdf")


def main_cli(args) -> int:
    try:
        result = ingest(args.source, out=args.out, max_pages=args.max_pages,
                        max_blocks=getattr(args, "max_blocks", DEFAULT_MAX_BLOCKS),
                        allow_repaired=getattr(args, "allow_repaired", False))
    except IngestError as exc:
        print(f"✗ {exc}", file=sys.stderr)
        return exc.code
    manifest = result.manifest
    print(f"已写入 {result.out_path}")
    if manifest["format"] == "docx":
        print(f"  {manifest['unit_count']} 块 / {manifest['total_chars']} 字 / "
              f"空块 {len(manifest['empty_units'])} / sha256 {manifest['source_sha256'][:12]}…")
    else:
        print(f"  {manifest['unit_count']} 页 / {manifest['total_chars']} 字 / "
              f"空页 {len(manifest['empty_pages'])} / sha256 {manifest['source_sha256'][:12]}…")
    for warning in manifest.get("warnings", []):
        print(f"  ⚠ {warning}")
    return 0
