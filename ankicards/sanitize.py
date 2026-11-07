"""HTML 净化：卡片与预览里只允许「排版用途」的标签，去掉可执行与外链内容。

背景：卡片正文来自文档/模型生成，属于不可信输入；Anki 与本地预览都会渲染 HTML。
白名单策略（而不是黑名单）更稳，但为了不破坏现有卡片的排版标记，这里做最小必要净化：
- 删除 script/style/iframe/object/embed/link/meta 等可执行或可挂载的标签；
- 删除所有 on* 事件属性；
- 外部 URL（http/https/protocol-relative/javascript）在 src/href 上被替换为 #。
保留：b/strong/i/em/u/br/hr/ul/ol/li/table/tr/th/td/p/div/span/img 等排版标签及其安全属性。
"""

from __future__ import annotations

import re

_BLOCKED_TAGS = ("script", "style", "iframe", "object", "embed", "link", "meta")
_BLOCK_RE = re.compile(
    r"(?is)<(?P<tag>" + "|".join(_BLOCKED_TAGS) + r")\b[^>]*>.*?</(?P=tag)\s*>")
_SELF_CLOSING_BLOCK_RE = re.compile(
    r"(?is)<(?:" + "|".join(_BLOCKED_TAGS) + r")\b[^>]*?/?>")
_EVENT_ATTR_RE = re.compile(r"(?is)\son[a-z]+\s*=\s*(\"[^\"]*\"|'[^']*'|[^\s>]+)")
_URL_ATTR_RE = re.compile(r"(?is)\b(src|href)\s*=\s*(\"([^\"]*)\"|'([^']*)')")
_UNSAFE_URL = re.compile(r"(?is)^\s*(https?:|//|javascript:|data:text/html)")


def _clean_url(match: re.Match) -> str:
    attr = match.group(1)
    raw = match.group(3) if match.group(3) is not None else match.group(4)
    if _UNSAFE_URL.match(raw or ""):
        return f'{attr}="#"'
    return match.group(0)


def sanitize_html(text: str) -> str:
    """净化一段卡片 HTML，返回可安全渲染的字符串。"""
    if not text:
        return text or ""
    cleaned = _BLOCK_RE.sub("", text)
    cleaned = _SELF_CLOSING_BLOCK_RE.sub("", cleaned)
    cleaned = _EVENT_ATTR_RE.sub("", cleaned)
    cleaned = _URL_ATTR_RE.sub(_clean_url, cleaned)
    return cleaned
