"""HTML 净化：卡片与预览只允许「排版用途」的标签与属性，去掉可执行与外链内容。

实现方式：用标准库 `HTMLParser` 做**白名单重建**，而不是正则删除。
正则版曾出现四类绕过（`<svg/onload>`、实体编码 `javascript:`、斜杠分隔属性、嵌套 `<script>`），
现在：
- 允许标签逐个重建，未知标签只丢标签、保留文本；
- `script/style` 连同内容整段丢弃；
- 只保留排版属性白名单，`on*` / `srcdoc` 一律丢弃；
- `src` / `href` 先做实体解码与去控制字符，再判协议：
  只放行相对路径与 `data:image/(png|jpeg|gif|webp)`，其余外部/协议 URL 直接去掉该属性。
"""

from __future__ import annotations

import html as html_lib
import re
from html.parser import HTMLParser

# 只保留排版语义；img 与 a 是唯一允许带 URL 的标签
ALLOWED_TAGS = {
    "b", "strong", "i", "em", "u", "s", "br", "hr", "p", "div", "span",
    "ul", "ol", "li", "table", "thead", "tbody", "tr", "th", "td",
    "blockquote", "code", "pre", "sub", "sup", "img", "a",
}
VOID_TAGS = {"br", "hr", "img"}
ALLOWED_ATTRS = {"class", "colspan", "rowspan", "alt", "title", "src", "href",
                 "width", "height"}
DROP_WITH_CONTENT = {"script", "style"}
_SAFE_DATA_IMAGE = re.compile(r"(?i)^data:image/(png|jpe?g|gif|webp)[;,]")
_SCHEME = re.compile(r"(?i)^[a-z][a-z0-9+.\-]*:")
_CONTROL = re.compile(r"[\x00-\x20]+")


class _Sanitizer(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.drop_depth = 0

    def _emit_start(self, tag: str, attrs) -> None:
        if self.drop_depth or tag not in ALLOWED_TAGS:
            return
        rendered = [f"<{tag}"]
        for name, value in attrs:
            name = name.lower()
            if name not in ALLOWED_ATTRS:
                continue
            if name in ("src", "href") and tag not in ("img", "a"):
                continue
            value = value or ""
            if name in ("src", "href"):
                safe = _safe_url(value)
                if safe is None:
                    continue
                value = safe
            rendered.append(f' {name}="{html_lib.escape(value, quote=True)}"')
        rendered.append(">")
        self.parts.append("".join(rendered))

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag in DROP_WITH_CONTENT:
            self.drop_depth += 1
            return
        self._emit_start(tag, attrs)

    def handle_startendtag(self, tag, attrs):
        tag = tag.lower()
        if tag in DROP_WITH_CONTENT:
            return  # 自闭合的 script/style 没有内容可丢
        self._emit_start(tag, attrs)

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in DROP_WITH_CONTENT:
            self.drop_depth = max(0, self.drop_depth - 1)
            return
        if self.drop_depth or tag not in ALLOWED_TAGS or tag in VOID_TAGS:
            return
        self.parts.append(f"</{tag}>")

    def handle_data(self, data):
        if not self.drop_depth:
            self.parts.append(html_lib.escape(data, quote=False))

    def result(self) -> str:
        return "".join(self.parts)


def _safe_url(value: str) -> str | None:
    """URL 属性白名单：相对路径与位图 data URL 放行，其余返回 None（去掉属性）。"""
    raw = html_lib.unescape(value).strip()
    compact = _CONTROL.sub("", raw).lower()
    if compact.startswith("data:"):
        return raw if _SAFE_DATA_IMAGE.match(compact) else None
    if compact.startswith("//") or _SCHEME.match(compact):
        return None
    return raw


def sanitize_html(text: str) -> str:
    """净化一段卡片 HTML，返回可安全渲染的字符串。"""
    if not text:
        return text or ""
    parser = _Sanitizer()
    try:
        parser.feed(text)
        parser.close()
    except Exception:  # noqa: BLE001 - 畸形 HTML 不能把整条构建打挂
        return html_lib.escape(text, quote=False)
    return parser.result()
