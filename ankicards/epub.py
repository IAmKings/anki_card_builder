"""把 EPUB 拆成可寻址的段落单元（chapter:C/p:M）。

只做解析，不做语义判断：章节顺序来自 OPF spine，正文复用 web.iter_html_blocks
（EPUB 正文就是 XHTML）。不处理 DRM、不下载远程资源、不执行脚本。
"""

from __future__ import annotations

import posixpath
import re
import zipfile
from pathlib import Path
from urllib.parse import unquote

from lxml import etree

from .errors import CardError
from .web import iter_html_blocks

CONTAINER_PATH = "META-INF/container.xml"
NS_CONTAINER = {"c": "urn:oasis:names:tc:opendocument:xmlns:container"}
NS_OPF = {"opf": "http://www.idpf.org/2007/opf"}
XHTML_TYPES = {"application/xhtml+xml", "text/html"}


def _read_xml(archive: zipfile.ZipFile, name: str):
    try:
        raw = archive.read(name)
    except KeyError as exc:
        raise CardError(f"EPUB 缺少 {name}（不是有效的 EPUB）") from exc
    try:
        return etree.fromstring(raw)
    except etree.XMLSyntaxError as exc:
        raise CardError(f"EPUB 里的 {name} 不是合法 XML: {exc}") from exc


def _resolve(base: str, href: str) -> str:
    target = unquote(href.split("#", 1)[0])
    path = posixpath.normpath(posixpath.join(base, target))
    if path.startswith("..") or path.startswith("/"):
        raise CardError(f"EPUB 里有越界路径: {href}")
    return path


def read_epub(path: str | Path, max_blocks: int = 5000
              ) -> tuple[list[dict], list[dict], list[str]]:
    """返回 (units, chapters, warnings)；unit 的 locator 是 chapter:C/p:M。"""
    units: list[dict] = []
    chapters: list[dict] = []
    warnings: list[str] = []
    try:
        archive = zipfile.ZipFile(path)
    except (zipfile.BadZipFile, OSError) as exc:
        raise CardError(f"不是有效的 EPUB（zip 打不开）: {exc}") from exc

    with archive:
        container = _read_xml(archive, CONTAINER_PATH)
        rootfile = container.find(".//c:rootfile", NS_CONTAINER)
        if rootfile is None or not rootfile.get("full-path"):
            raise CardError("EPUB 的 container.xml 没有 rootfile")
        opf_path = rootfile.get("full-path")
        opf = _read_xml(archive, opf_path)
        base = posixpath.dirname(opf_path)

        manifest: dict[str, tuple[str, str]] = {}
        for item in opf.findall(".//opf:manifest/opf:item", NS_OPF):
            item_id, href = item.get("id"), item.get("href")
            if item_id and href:
                manifest[item_id] = (href, item.get("media-type", ""))
        spine = [ref.get("idref") for ref in opf.findall(".//opf:spine/opf:itemref", NS_OPF)]
        if not spine:
            raise CardError("EPUB 的 OPF 没有 spine（读不出章节顺序）")

        for index, idref in enumerate(spine, 1):
            href, media = manifest.get(idref or "", (None, ""))
            if not href or media not in XHTML_TYPES:
                warnings.append(f"跳过 spine 第 {index} 章（{idref}）：不是 XHTML")
                continue
            name = _resolve(base, href)
            try:
                raw = archive.read(name)
            except KeyError:
                warnings.append(f"跳过 spine 第 {index} 章：zip 里没有 {name}")
                continue
            # lxml 不接受「已解码的字符串 + encoding 声明」，先摘掉 XML 声明。
            raw = re.sub(rb"^\s*<\?xml[^>]*\?>", b"", raw)
            blocks = list(iter_html_blocks(raw, max_blocks=max_blocks))
            title = next((b.text.strip() for b in blocks
                          if b.kind == "heading" and b.text.strip()), "")
            chapters.append({"index": index, "title": title or f"第 {index} 章", "units": 0})
            for pos, block in enumerate(blocks, 1):
                if len(units) >= max_blocks:
                    raise CardError(
                        f"段落数超过上限 {max_blocks}；请拆分或用 --max-blocks 放宽。")
                text = block.text.strip()
                if not text:
                    continue
                locator = f"chapter:{index}/p:{pos}"
                units.append({"id": locator, "locator": locator, "chapter": index,
                              "kind": block.kind, "chars": len(text), "text": text})
                chapters[-1]["units"] += 1

    if not units:
        raise CardError("EPUB 里没有可提取文本（可能是图片/漫画书，本工具不含 OCR）。")
    return units, chapters, warnings
