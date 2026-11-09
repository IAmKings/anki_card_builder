"""静态 HTML 的可见文本提取：标题、段落、列表项、表格行 -> block:N。

只做静态 DOM 解析，不执行 JS、不下载图片/样式/脚本，也不处理登录态。
`iter_html_blocks` 是 ingest 与 web-points 适配器的唯一遍历实现，避免两套索引漂移。
"""

from __future__ import annotations

import ipaddress
import re
import socket
from dataclasses import dataclass
from typing import Iterator
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import (
    HTTPRedirectHandler, ProxyHandler, Request, build_opener,
)

from lxml import etree
from lxml import html as lxml_html

from .errors import CardError

DEFAULT_MAX_WEB_BLOCKS = 5000
DEFAULT_WEB_TIMEOUT = 20
DEFAULT_MAX_BYTES = 5 * 1024 * 1024
DEFAULT_MAX_REDIRECTS = 5
_WS = re.compile(r"\s+")
_DROP_TAGS = ("script", "style", "noscript", "nav", "footer", "aside")
_BLOCK_TAGS = ("h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "tr")
_NESTED_TAGS = {"p", "li", "tr"}


class WebError(CardError):
    """HTML 解析失败；由 ingest 转成 IngestError（exit 2）。"""


@dataclass
class HtmlBlock:
    kind: str       # heading / paragraph / list_item / table_row
    locator: str    # block:N
    text: str


def _normalize(text: str) -> str:
    return _WS.sub(" ", text or "").strip()


def _element_text(element) -> str:
    return _normalize(" ".join(element.itertext()))


def _table_row_text(element) -> str:
    cells: list[str] = []
    for cell in element.xpath("./th|./td"):
        value = _element_text(cell)
        if not value:
            continue
        if cells and cells[-1] == value:
            continue
        cells.append(value)
    return " | ".join(cells)


def _has_block_ancestor(element, root) -> bool:
    parent = element.getparent()
    while parent is not None and parent is not root:
        if isinstance(parent.tag, str) and parent.tag.lower() in _NESTED_TAGS:
            return True
        parent = parent.getparent()
    return False


def iter_html_blocks(html: bytes | str, max_blocks: int = DEFAULT_MAX_WEB_BLOCKS,
                     encoding: str = "utf-8") -> Iterator[HtmlBlock]:
    """按 DOM 顺序产出有效文本块；空块不计入 block:N。"""
    if isinstance(html, bytes):
        try:
            html = html.decode(encoding)
        except (LookupError, UnicodeDecodeError):
            html = html.decode("utf-8", errors="replace")
    try:
        root = lxml_html.fromstring(html)
    except (etree.ParserError, ValueError, TypeError) as exc:
        raise WebError(f"无法解析 HTML: {exc}") from exc
    body = root.find("body")
    scope = body if body is not None else root
    for tag in _DROP_TAGS:
        for node in scope.xpath(f".//{tag}"):
            node.drop_tree()

    count = 0
    for element in scope.iter():
        tag = element.tag.lower() if isinstance(element.tag, str) else ""
        if tag not in _BLOCK_TAGS:
            continue
        if _has_block_ancestor(element, scope):
            continue
        if tag == "tr":
            text = _table_row_text(element)
        else:
            text = _element_text(element)
        if not text:
            continue
        count += 1
        if count > max_blocks:
            raise WebError(
                f"HTML 有效块超过 {max_blocks} 个；请拆分页面，或用 --max-blocks 放宽")
        kind = ("heading" if tag.startswith("h") else
                "paragraph" if tag == "p" else
                "list_item" if tag == "li" else "table_row")
        yield HtmlBlock(kind=kind, locator=f"block:{count}", text=text)


@dataclass
class FetchedHtml:
    content: bytes
    final_url: str
    content_type: str
    charset: str | None = None


def _is_private_ip(value: str) -> bool:
    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        return True
    return (address.is_private or address.is_loopback or address.is_link_local
            or address.is_reserved or address.is_multicast or address.is_unspecified)


def _validate_url(url: str, allow_private_network: bool = False) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise WebError(f"只允许 http/https URL，实际为 {parsed.scheme or '(无 scheme)'}")
    if not parsed.hostname:
        raise WebError(f"URL 缺少主机名: {url}")
    if parsed.username or parsed.password:
        raise WebError("URL 不能包含账号/密码")
    if allow_private_network:
        return
    try:
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        infos = socket.getaddrinfo(parsed.hostname, port,
                                   type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise WebError(f"无法解析主机名 {parsed.hostname}: {exc}") from exc
    if any(_is_private_ip(info[4][0]) for info in infos):
        raise WebError(
            f"拒绝访问内网/回环地址 {parsed.hostname}；如确需抓取本机页面，"
            "请加 --allow-private-network")


class _SafeRedirect(HTTPRedirectHandler):
    max_redirections = DEFAULT_MAX_REDIRECTS

    def __init__(self, allow_private_network: bool = False):
        super().__init__()
        self.allow_private_network = allow_private_network

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        target = urljoin(req.full_url, newurl)
        _validate_url(target, self.allow_private_network)
        return super().redirect_request(req, fp, code, msg, headers, target)


def fetch_html(url: str, timeout: float = DEFAULT_WEB_TIMEOUT,
               max_bytes: int | None = None,
               allow_private_network: bool = False) -> FetchedHtml:
    """抓取单个静态 HTML 页面；只读、不执行 JS、不带 Cookie/Authorization。"""
    _validate_url(url, allow_private_network)
    limit = DEFAULT_MAX_BYTES if max_bytes is None else max_bytes
    opener = build_opener(ProxyHandler({}), _SafeRedirect(allow_private_network))
    request = Request(url, headers={
        "User-Agent": "anki-card-builder/0.3 (+static-html)",
        "Accept": "text/html,application/xhtml+xml",
    })
    try:
        with opener.open(request, timeout=timeout) as response:
            content_type = response.headers.get_content_type()
            if content_type not in ("text/html", "application/xhtml+xml"):
                raise WebError(f"URL 返回的不是 HTML（Content-Type: {content_type}）")
            declared = response.headers.get("Content-Length")
            if declared and declared.isdigit() and int(declared) > limit:
                raise WebError(f"页面约 {int(declared) // 1024} KB，超过 {limit // 1024} KB 上限")
            chunks: list[bytes] = []
            total = 0
            while True:
                chunk = response.read(min(65536, limit - total + 1))
                if not chunk:
                    break
                chunks.append(chunk)
                total += len(chunk)
                if total > limit:
                    raise WebError(f"页面超过 {limit // 1024} KB 上限；请精简页面。")
            return FetchedHtml(b"".join(chunks), response.geturl(), content_type,
                               response.headers.get_content_charset())
    except HTTPError as exc:
        raise WebError(f"HTTP {exc.code}: {exc.reason}") from exc
    except URLError as exc:
        raise WebError(f"抓取失败: {exc.reason}") from exc
    except (TimeoutError, socket.timeout) as exc:
        raise WebError(f"抓取超时（{timeout} 秒）") from exc
    except OSError as exc:
        raise WebError(f"抓取失败: {exc}") from exc
