"""PDF 文本摄取：把「有文本层的 PDF」变成可寻址的逐页文本。

首版范围（已与用户确认）：
- 只支持文本型 PDF；扫描件（无文本层）明确拒绝，不做 OCR。
- DOCX/MD/TXT 在命令层直接拒绝：DOCX 无“页”概念且表格/页眉抽取未实现；
  MD/TXT 请走 `import --adapter`。
- 输出固定写到 .work/ingest/（被 .gitignore 忽略），并带源文件 sha256。
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

DEFAULT_MAX_PAGES = 2000
EMPTY_PAGE_RATIO_LIMIT = 0.2


@dataclass
class IngestResult:
    """摄取结果：manifest 是落盘内容，out_path 是实际写入位置。"""

    manifest: dict
    out_path: Path


class IngestError(Exception):
    """摄取失败；code 为进程退出码（2 = 输入/环境问题）。"""

    def __init__(self, message: str, code: int = 2):
        super().__init__(message)
        self.code = code


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _reject_unsupported(path: Path) -> None:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return
    if suffix == ".docx":
        raise IngestError(
            "首版不支持 DOCX：Word 没有“页”概念，且表格/页眉抽取尚未实现。"
            "请先在 Word/WPS 里导出为 PDF，再运行 ingest。")
    if suffix in (".md", ".markdown", ".txt"):
        raise IngestError(
            f"{suffix} 不是 PDF；请用 `python3 -m ankicards import <目录> --adapter <名字>`。")
    raise IngestError(f"不支持的文件类型: {suffix or '(无扩展名)'}")


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
    _reject_unsupported(path)

    try:
        import pymupdf  # type: ignore
    except ImportError as exc:  # pragma: no cover - 依赖环境
        raise IngestError(
            "需要 PyMuPDF 才能摄取 PDF：pip install -r requirements-render.txt") from exc

    sha = _sha256(path)
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
    if empty_ratio >= 0.5:
        raise IngestError(
            f"{len(empty_pages)}/{len(units)} 页没有文本（≥50%），疑似扫描件或排版异常页："
            f"空页 = {empty_pages[:20]}{'…' if len(empty_pages) > 20 else ''}")
    if empty_ratio > EMPTY_PAGE_RATIO_LIMIT:
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


def load_ingest(path: str | Path) -> dict[int, str]:
    """读 ingest 产物，返回 page -> text，供 check 的溯源闸门使用。"""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise IngestError(f"无法读取 ingest 产物 {path}: {exc}") from exc
    units = data.get("units")
    if not isinstance(units, list):
        raise IngestError(f"{path} 不是有效的 ingest 产物（缺少 units）")
    pages: dict[int, str] = {}
    for unit in units:
        page = unit.get("page")
        if isinstance(page, int):
            pages[page] = str(unit.get("text", ""))
    if not pages:
        raise IngestError(f"{path} 里没有任何页面")
    return pages


def main_cli(args) -> int:
    try:
        result = ingest_pdf(args.source, out=args.out, max_pages=args.max_pages,
                            allow_repaired=getattr(args, "allow_repaired", False))
    except IngestError as exc:
        print(f"✗ {exc}", file=sys.stderr)
        return exc.code
    manifest = result.manifest
    print(f"已写入 {result.out_path}")
    print(f"  {manifest['unit_count']} 页 / {manifest['total_chars']} 字 / "
          f"空页 {len(manifest['empty_pages'])} / sha256 {manifest['source_sha256'][:12]}…")
    for warning in manifest.get("warnings", []):
        print(f"  ⚠ {warning}")
    return 0
