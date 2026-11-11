"""文本摄取：PDF 逐页、DOCX 逐段/逐表格行，产出可寻址的 JSON 清单。

支持范围（已与用户确认）：
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
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from .docx import iter_docx_blocks
from .errors import CardError
from .epub import read_epub
from .grouping import (
    classify_docx_block, classify_epub_block, classify_txt_line,
    classify_web_block, group_units, missing_units,
)
from .quality import SENTENCE_END
from .txt import iter_txt_lines
from .schema import load_json
from .web import (
    DEFAULT_WEB_TIMEOUT, WebError, fetch_html, iter_html_blocks,
)

DEFAULT_MAX_PAGES = 2000
DEFAULT_MAX_BLOCKS = 5000
DEFAULT_MAX_LINES = 50000
DEFAULT_TXT_ENCODING = "utf-8-sig"
MAX_TXT_BYTES = 10 * 1024 * 1024
EMPTY_LINE_RATIO_LIMIT = 0.5
MAX_DOCX_BYTES = 20 * 1024 * 1024
MAX_DOCX_UNCOMPRESSED_BYTES = 200 * 1024 * 1024
MAX_WEB_BYTES = 5 * 1024 * 1024
EMPTY_PAGE_RATIO_LIMIT = 0.2   # 超过即给 warning
EMPTY_FAIL_RATIO = 0.5         # 达到即拒绝


def _groups(units: list[dict], classify, fmt: str) -> list[dict]:
    """给 ingest 产物算 groups，并自检「每个非空单元都被归组」。"""
    groups = group_units(units, classify)
    uncovered = missing_units(units, groups)
    if uncovered:
        sample = "、".join(uncovered[:5])
        raise IngestError(
            f"{fmt} 分组自检失败：{len(uncovered)} 个非空单元没有归组（{sample}）；"
            "这是分组规则的问题，请报 issue。")
    return groups


@dataclass
class IngestData:
    """load_ingest 的返回值：页码/定位→文本 + 源文件 sha256（可能缺省）。"""

    pages: dict[int, str]
    source_sha256: str | None = None
    format: str = "pdf"
    locators: dict[str, str] = field(default_factory=dict)
    #: 分组记录（grouping.group_units 的产物）；PDF 与旧版清单里为空。
    groups: list[dict] = field(default_factory=list)


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


def _page_spans(pages: dict[int, str]) -> list[dict]:
    """找出跨页续写的相邻页对：上一页不以句末标点收尾，下一页紧接下文。

    PDF 的定位单位是页，一段话常被页码切断；这里只记录「可能的续页」，
    真正的取舍仍由人在 plan 里决定（quote 需要覆盖哪两页就写 page:N-N+1）。
    """
    spans: list[dict] = []
    numbers = sorted(pages)
    for left_no, right_no in zip(numbers, numbers[1:]):
        left = (pages[left_no] or "").rstrip()
        right = (pages[right_no] or "").lstrip()
        if not left or not right:
            continue
        if left[-1] in SENTENCE_END:
            continue
        spans.append({
            "id": f"span:{left_no}",
            "locator": f"page:{left_no}-{right_no}",
            "pages": [left_no, right_no],
            "chars": len(left) + len(right),
        })
    return spans


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

    pages_text = {unit["page"]: unit["text"] for unit in units}
    page_spans = _page_spans(pages_text)
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
        "page_spans": page_spans,
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
    from docx.opc.exceptions import PackageNotFoundError
    from lxml.etree import XMLSyntaxError
    try:
        doc = docx.Document(str(path))
    except (PackageNotFoundError, zipfile.BadZipFile, XMLSyntaxError,
            KeyError, ValueError, OSError) as exc:
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
        "groups": _groups(units, classify_docx_block, "docx"),
        "units": units,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(manifest, ensure_ascii=False, indent=1, sort_keys=True) + "\n"
    out_path.write_text(payload, encoding="utf-8")
    return IngestResult(manifest=manifest, out_path=out_path)


def ingest_epub(epub_path: str | Path, out: str | Path | None = None,
                max_blocks: int = DEFAULT_MAX_BLOCKS,
                repo_root: Path | None = None) -> IngestResult:
    """把 .epub 拆成 chapter:C/p:M 的段落清单（章节顺序来自 spine）。"""
    path = Path(epub_path).expanduser().resolve()
    if not path.exists():
        raise IngestError(f"找不到文件: {path}")
    if not path.is_file():
        raise IngestError(f"不是文件: {path}")
    if path.suffix.lower() != ".epub":
        raise IngestError(f"只支持 .epub；{path.suffix or '(无扩展名)'} 请先转换格式")

    sha = file_sha256(path)
    out_path = Path(out).expanduser() if out else _default_out(path, sha)
    _check_out_path(out_path, repo_root)

    try:
        units, chapters, warnings = read_epub(path, max_blocks=max_blocks)
    except CardError as exc:
        raise IngestError(str(exc)) from exc
    total_chars = sum(unit["chars"] for unit in units)
    manifest = {
        "format": "epub",
        "source": path.name,
        "source_sha256": sha,
        "unit_kind": "block",
        "chapter_count": len(chapters),
        "unit_count": len(units),
        "total_chars": total_chars,
        "chapters": chapters,
        "warnings": warnings,
        "engine": "zipfile+lxml",
        "groups": _groups(units, classify_epub_block, "epub"),
        "units": units,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(manifest, ensure_ascii=False, indent=1, sort_keys=True) + "\n"
    out_path.write_text(payload, encoding="utf-8")
    return IngestResult(manifest=manifest, out_path=out_path)


def ingest_txt(txt_path: str | Path, out: str | Path | None = None,
               max_lines: int = DEFAULT_MAX_LINES,
               encoding: str = DEFAULT_TXT_ENCODING,
               repo_root: Path | None = None) -> IngestResult:
    """把 .txt 按物理行抽成 line:N 清单。"""
    path = Path(txt_path).expanduser().resolve()
    if not path.exists():
        raise IngestError(f"找不到文件: {path}")
    if not path.is_file():
        raise IngestError(f"不是文件: {path}")
    suffix = path.suffix.lower()
    if suffix != ".txt":
        raise IngestError(f"只支持 .txt；{suffix or '(无扩展名)'} 请另存为 .txt")
    if path.stat().st_size > MAX_TXT_BYTES:
        raise IngestError(
            f"TXT 超过 {MAX_TXT_BYTES // (1024 * 1024)} MB 上限；请拆分文件。")

    sha = file_sha256(path)
    out_path = Path(out).expanduser() if out else _default_out(path, sha)
    _check_out_path(out_path, repo_root)

    try:
        text = path.read_text(encoding=encoding)
    except LookupError as exc:
        raise IngestError(f"未知编码: {encoding}") from exc
    except UnicodeDecodeError as exc:
        raise IngestError(
            f"无法按 {encoding} 解码 {path.name}；请用 --encoding 指定正确编码（如 gb18030）。"
        ) from exc
    except OSError as exc:
        raise IngestError(f"无法读取 TXT: {exc}") from exc

    lines = text.splitlines()
    if not lines:
        raise IngestError("没有可提取文本：TXT 是空文件。")
    if len(lines) > max_lines:
        raise IngestError(
            f"行数 {len(lines)} 超过上限 {max_lines}；请拆分文件或用 --max-lines 放宽。")

    units = []
    empty_lines = []
    for item in iter_txt_lines(text):
        if item.chars == 0:
            empty_lines.append(item.line)
        units.append({
            "id": f"line:{item.line}",
            "line": item.line,
            "chars": item.chars,
            "text": item.text,
        })

    total_chars = sum(unit["chars"] for unit in units)
    if total_chars == 0:
        raise IngestError("没有可提取文本：TXT 只有空行/空白。")

    warnings: list[str] = []
    empty_ratio = len(empty_lines) / len(units)
    if empty_ratio >= EMPTY_LINE_RATIO_LIMIT:
        warnings.append(
            f"{len(empty_lines)}/{len(units)} 行为空行"
            f"（>{int(EMPTY_LINE_RATIO_LIMIT * 100)}%）；引用这些行的卡片会被闸门拦下")

    manifest = {
        "format": "txt",
        "source": path.name,
        "source_sha256": sha,
        "encoding": encoding,
        "unit_kind": "line",
        "unit_count": len(units),
        "total_chars": total_chars,
        "empty_lines": empty_lines,
        "warnings": warnings,
        "groups": _groups(units, classify_txt_line, "txt"),
        "units": units,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(manifest, ensure_ascii=False, indent=1, sort_keys=True) + "\n"
    out_path.write_text(payload, encoding="utf-8")
    return IngestResult(manifest=manifest, out_path=out_path)



def ingest_html(html_path: str | Path, out: str | Path | None = None,
                max_blocks: int = DEFAULT_MAX_BLOCKS,
                max_bytes: int | None = None,
                repo_root: Path | None = None) -> IngestResult:
    """把本地 .html/.htm 的可见块抽成 block:N 清单（不执行 JS）。"""
    path = Path(html_path).expanduser().resolve()
    if not path.exists():
        raise IngestError(f"找不到文件: {path}")
    if not path.is_file():
        raise IngestError(f"不是文件: {path}")
    suffix = path.suffix.lower()
    if suffix not in (".html", ".htm"):
        raise IngestError(f"只支持 .html/.htm；{suffix or '(无扩展名)'} 不是网页文件")
    limit = MAX_WEB_BYTES if max_bytes is None else max_bytes
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise IngestError(f"无法读取 HTML: {exc}") from exc
    if size > limit:
        raise IngestError(
            f"HTML 文件约 {size // 1024} KB，超过 {limit // 1024} KB 上限；请精简页面。")
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise IngestError(f"无法读取 HTML: {exc}") from exc
    sha = hashlib.sha256(raw).hexdigest()
    try:
        blocks = list(iter_html_blocks(raw, max_blocks=max_blocks))
    except WebError as exc:
        raise IngestError(str(exc)) from exc
    if not blocks:
        raise IngestError("没有可提取文本：HTML 里没有标题/段落/列表/表格文本。")
    units = [{
        "id": block.locator,
        "locator": block.locator,
        "kind": block.kind,
        "chars": len(block.text),
        "text": block.text,
    } for block in blocks]
    total_chars = sum(unit["chars"] for unit in units)
    if total_chars == 0:
        raise IngestError("没有可提取文本：HTML 里的可见块都是空白。")
    manifest = {
        "format": "web",
        "source": path.name,
        "source_sha256": sha,
        "unit_kind": "block",
        "unit_count": len(units),
        "total_chars": total_chars,
        "warnings": [],
        "groups": _groups(units, classify_web_block, "web"),
        "units": units,
    }
    out_path = Path(out).expanduser().resolve() if out else _default_out(path, sha)
    _check_out_path(out_path, repo_root=repo_root)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(manifest, ensure_ascii=False, indent=1, sort_keys=True) + "\n"
    out_path.write_text(payload, encoding="utf-8")
    return IngestResult(manifest=manifest, out_path=out_path)



def _default_out_url(url: str, sha: str) -> Path:
    parsed = urlparse(url)
    host = re.sub(r"[^\w\-]+", "_", parsed.netloc)[:30] or "web"
    stem = re.sub(r"[^\w\-]+", "_", Path(parsed.path).stem)[:30] or "index"
    return Path.cwd() / ".work" / "ingest" / f"{host}-{stem}-{sha[:8]}.json"


def ingest_url(url: str, out: str | Path | None = None,
               max_blocks: int = DEFAULT_MAX_BLOCKS,
               max_bytes: int | None = None,
               timeout: float = DEFAULT_WEB_TIMEOUT,
               allow_private_network: bool = False,
               repo_root: Path | None = None) -> IngestResult:
    """抓取单个静态 HTML URL，抽成 block:N 清单；不执行 JS、不跟随外部资源。"""
    try:
        fetched = fetch_html(url, timeout=timeout, max_bytes=max_bytes,
                             allow_private_network=allow_private_network)
    except WebError as exc:
        raise IngestError(str(exc)) from exc
    try:
        blocks = list(iter_html_blocks(fetched.content, max_blocks=max_blocks,
                                          encoding=fetched.charset or "utf-8"))
    except WebError as exc:
        raise IngestError(str(exc)) from exc
    if not blocks:
        raise IngestError("没有可提取文本：URL 里没有标题/段落/列表/表格文本。")
    units = [{
        "id": block.locator,
        "locator": block.locator,
        "kind": block.kind,
        "chars": len(block.text),
        "text": block.text,
    } for block in blocks]
    total_chars = sum(unit["chars"] for unit in units)
    if total_chars == 0:
        raise IngestError("没有可提取文本：URL 里的可见块都是空白。")
    content_sha = hashlib.sha256(fetched.content).hexdigest()
    manifest = {
        "format": "web",
        "source": url,
        "final_url": fetched.final_url,
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "content_type": fetched.content_type,
        "content_sha256": content_sha,
        "source_sha256": None,
        "unit_kind": "block",
        "unit_count": len(units),
        "total_chars": total_chars,
        "warnings": [],
        "groups": _groups(units, classify_web_block, "web"),
        "units": units,
    }
    out_path = Path(out).expanduser().resolve() if out else _default_out_url(url, content_sha)
    _check_out_path(out_path, repo_root=repo_root)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(manifest, ensure_ascii=False, indent=1, sort_keys=True) + "\n"
    out_path.write_text(payload, encoding="utf-8")
    return IngestResult(manifest=manifest, out_path=out_path)


def ingest(source: str | Path, out: str | Path | None = None,
           max_pages: int = DEFAULT_MAX_PAGES,
           max_blocks: int = DEFAULT_MAX_BLOCKS,
           max_lines: int = DEFAULT_MAX_LINES,
           encoding: str = DEFAULT_TXT_ENCODING,
           max_bytes: int | None = None,
           timeout: float = DEFAULT_WEB_TIMEOUT,
           allow_private_network: bool = False,
           allow_repaired: bool = False,
           repo_root: Path | None = None) -> IngestResult:
    """按扩展名分派：.pdf / .docx / .txt / .html / .htm，或抓取 http(s) URL。"""
    raw = str(source).strip()
    if raw.startswith(("http://", "https://")):
        return ingest_url(raw, out=out, max_blocks=max_blocks, max_bytes=max_bytes,
                          timeout=timeout, allow_private_network=allow_private_network,
                          repo_root=repo_root)
    path = Path(raw).expanduser().resolve()
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return ingest_pdf(path, out=out, max_pages=max_pages,
                          allow_repaired=allow_repaired, repo_root=repo_root)
    if suffix == ".epub":
        return ingest_epub(path, out=out, max_blocks=max_blocks, repo_root=repo_root)
    if suffix == ".docx":
        return ingest_docx(path, out=out, max_blocks=max_blocks, repo_root=repo_root)
    if suffix == ".txt":
        return ingest_txt(path, out=out, max_lines=max_lines, encoding=encoding,
                          repo_root=repo_root)
    if suffix in (".html", ".htm"):
        return ingest_html(path, out=out, max_blocks=max_blocks, max_bytes=max_bytes,
                           repo_root=repo_root)
    if suffix in (".doc", ".docm"):
        raise IngestError(f"只支持 .docx；{suffix} 请先另存为 .docx")
    if suffix in (".md", ".markdown"):
        raise IngestError(
            f"{suffix} 不是 PDF/DOCX/TXT/EPUB/HTML；"
            "请用 `python3 -m ankicards import --adapter`，或先转成支持的格式。")
    raise IngestError(f"不支持的文件类型: {suffix or '(无扩展名)'}")


def _add_group_locators(data: dict, locators: dict[str, str],
                        path: str | Path) -> list[dict]:
    """把分组区间（line:3-7）注册为定位，并返回分组记录。"""
    groups = data.get("groups")
    if groups is None:
        return []
    if not isinstance(groups, list):
        raise IngestError(f"{path}: groups 必须是数组")
    for group in groups:
        if not isinstance(group, dict):
            raise IngestError(f"{path}: groups 里必须是对象")
        locator = group.get("locator")
        members = group.get("unit_locators")
        if not isinstance(locator, str) or not locator:
            raise IngestError(f"{path}: group 缺少 locator")
        if not isinstance(members, list) or not members:
            raise IngestError(f"{path}: group {locator} 缺少 unit_locators")
        if locator in locators:
            if len(members) == 1 and members[0] == locator:
                continue      # 单成员组的定位就是单元定位，已在 locators 里
            raise IngestError(f"{path}: group 定位与单元定位冲突: {locator}")
        texts = []
        for member in members:
            if not isinstance(member, str) or member not in locators:
                raise IngestError(f"{path}: group {locator} 引用了不存在的单元 {member!r}")
            texts.append(locators[member])
        if not "".join(texts).strip():
            raise IngestError(f"{path}: group {locator} 的文本是空的")
        locators[locator] = "\n".join(texts)
    return groups


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
    if fmt not in (None, "pdf", "docx", "txt", "web", "epub"):
        raise IngestError(f"{path}: format 必须是 pdf/docx/txt/web/epub，实际为 {fmt!r}")
    if fmt is None:
        first = units[0] if units else None
        if isinstance(first, dict) and "chapter" in first:
            fmt = "epub"
        elif isinstance(first, dict) and "locator" in first:
            fmt = "docx"
        elif isinstance(first, dict) and "line" in first:
            fmt = "txt"
        else:
            fmt = "pdf"

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
        groups = _add_group_locators(data, locators, path)
        return IngestData(pages={}, source_sha256=sha, format="docx",
                          locators=locators, groups=groups)

    if fmt == "epub":
        locators: dict[str, str] = {}
        for unit in units:
            if not isinstance(unit, dict):
                raise IngestError(f"{path}: units 必须是对象数组")
            locator = unit.get("locator") or unit.get("id")
            if not isinstance(locator, str) or not locator:
                raise IngestError(f"{path}: EPUB unit 缺少 locator")
            if locator in locators:
                raise IngestError(f"{path}: EPUB locator 重复: {locator}")
            locators[locator] = str(unit.get("text", ""))
        if not locators:
            raise IngestError(f"{path} 里没有任何段落")
        groups = _add_group_locators(data, locators, path)
        return IngestData(pages={}, source_sha256=sha, format="epub",
                          locators=locators, groups=groups)

    if fmt == "web":
        locators: dict[str, str] = {}
        for unit in units:
            if not isinstance(unit, dict):
                raise IngestError(f"{path}: units 必须是对象数组")
            locator = unit.get("locator") or unit.get("id")
            if not isinstance(locator, str) or not locator:
                raise IngestError(f"{path}: WEB unit 缺少 locator")
            if locator in locators:
                raise IngestError(f"{path}: WEB locator 重复: {locator}")
            locators[locator] = str(unit.get("text", ""))
        if not locators:
            raise IngestError(f"{path} 里没有任何网页文本块")
        groups = _add_group_locators(data, locators, path)
        return IngestData(pages={}, source_sha256=sha, format="web",
                          locators=locators, groups=groups)

    if fmt == "txt":
        locators: dict[str, str] = {}
        for unit in units:
            if not isinstance(unit, dict):
                raise IngestError(f"{path}: units 必须是对象数组")
            line = unit.get("line")
            if not isinstance(line, int) or isinstance(line, bool) or line < 1:
                raise IngestError(f"{path}: TXT unit 缺少正整数 line")
            locator = unit.get("id") or f"line:{line}"
            if not isinstance(locator, str) or not locator:
                raise IngestError(f"{path}: TXT unit 缺少 locator")
            if locator in locators:
                raise IngestError(f"{path}: TXT locator 重复: {locator}")
            locators[locator] = str(unit.get("text", ""))
        if not locators:
            raise IngestError(f"{path} 里没有任何行")
        groups = _add_group_locators(data, locators, path)
        return IngestData(pages={}, source_sha256=sha, format="txt",
                          locators=locators, groups=groups)

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
                        max_lines=getattr(args, "max_lines", DEFAULT_MAX_LINES),
                        encoding=getattr(args, "encoding", DEFAULT_TXT_ENCODING),
                        max_bytes=getattr(args, "max_bytes", None),
                        timeout=getattr(args, "timeout", DEFAULT_WEB_TIMEOUT),
                        allow_private_network=getattr(args, "allow_private_network", False),
                        allow_repaired=getattr(args, "allow_repaired", False))
    except IngestError as exc:
        print(f"✗ {exc}", file=sys.stderr)
        return exc.code
    manifest = result.manifest
    print(f"已写入 {result.out_path}")
    if manifest["format"] == "docx":
        print(f"  {manifest['unit_count']} 块 / {manifest['total_chars']} 字 / "
              f"空块 {len(manifest['empty_units'])} / sha256 {manifest['source_sha256'][:12]}…")
    elif manifest["format"] == "txt":
        print(f"  {manifest['unit_count']} 行 / {manifest['total_chars']} 字 / "
              f"空行 {len(manifest['empty_lines'])} / sha256 {manifest['source_sha256'][:12]}…")
    elif manifest["format"] == "epub":
        print(f"  {manifest['chapter_count']} 章 / {manifest['unit_count']} 段 / "
              f"{manifest['total_chars']} 字 / sha256 {manifest['source_sha256'][:12]}…")
    elif manifest["format"] == "web":
        sha = manifest.get("content_sha256") or manifest.get("source_sha256") or ""
        print(f"  {manifest['unit_count']} 块 / {manifest['total_chars']} 字 / "
              f"sha256 {sha[:12]}…")
        if manifest.get("final_url") and manifest["final_url"] != manifest["source"]:
            print(f"  最终地址：{manifest['final_url']}")
    else:
        print(f"  {manifest['unit_count']} 页 / {manifest['total_chars']} 字 / "
              f"空页 {len(manifest['empty_pages'])} / sha256 {manifest['source_sha256'][:12]}…")
    for warning in manifest.get("warnings", []):
        print(f"  ⚠ {warning}")
    return 0
