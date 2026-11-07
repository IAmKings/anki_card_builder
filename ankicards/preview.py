"""单文件 HTML 预览：把整副牌摊开看问题、答案与配图。

图片只内嵌一份（data-k 占位 + 脚本挂载），避免同一页截图在几百张卡里重复膨胀。
需要 PDF 才能显示原文页截图与裁图；没有 PDF 时只渲染文字部分。
"""

from __future__ import annotations

import base64
import html
import json
import re
from pathlib import Path

from .sanitize import sanitize_html
from .schema import DeckSpec

_CSS = """
:root{--gold:#9a7b4f;--line:#e3d8c4;--ink:#23201c;--muted:#8a8378;}
*{box-sizing:border-box}
body{margin:0;background:#f4f1ea;color:var(--ink);
font-family:"PingFang SC","Hiragino Sans GB","Microsoft YaHei","Songti SC",serif;line-height:1.62}
header{padding:44px 28px 26px;background:#1f1c18;color:#f4f1ea}
header h1{margin:0 0 8px;font-size:26px;letter-spacing:.06em;font-weight:600}
header p{margin:0;color:#c9b48b;font-size:14px;letter-spacing:.04em}
nav{padding:12px 28px;background:#fff;border-bottom:1px solid var(--line);position:sticky;top:0;z-index:5;
display:flex;flex-wrap:wrap;gap:8px;align-items:center}
nav a{font-size:13px;color:#5b5348;text-decoration:none;border:1px solid var(--line);
padding:3px 10px;border-radius:14px}
nav a:hover{border-color:var(--gold);color:var(--gold)}
nav button{font:inherit;font-size:12px;color:#5b5348;background:#fff;border:1px solid var(--line);
border-radius:14px;padding:3px 10px;cursor:pointer}
nav button:hover{border-color:var(--gold);color:var(--gold)}
main{padding:26px 20px 80px;max-width:1180px;margin:0 auto}
section{margin:0 0 44px}
h2{font-size:19px;letter-spacing:.05em;color:#3b352c;border-left:3px solid var(--gold);
padding-left:10px;margin:28px 0 16px}
h2 small{font-weight:400;color:var(--muted);font-size:13px;margin-left:6px}
.card{background:#fbf9f5;border:1px solid var(--line);border-radius:8px;padding:18px 20px;margin:0 0 16px;
box-shadow:0 1px 2px rgba(0,0,0,.03)}
.kicker{font-size:11.5px;letter-spacing:.12em;color:var(--gold);text-transform:uppercase;
border-bottom:1px solid var(--line);padding-bottom:5px;margin-bottom:12px}
.q{font-size:17.5px;font-weight:600;margin:0 0 10px}
.grid{display:grid;grid-template-columns:1fr 300px;gap:18px;align-items:start}
@media(max-width:760px){.grid{grid-template-columns:1fr}}
.a b{color:#7a5c2e}
.a ul{padding-left:18px;margin:6px 0}
.a li{margin:3px 0}
.a table{border-collapse:collapse;width:100%;font-size:14px;margin:8px 0}
.a th,.a td{border:1px solid var(--line);padding:5px 8px;vertical-align:top}
.a th{background:#f3ece0}
.cloze{color:#7a5c2e;font-weight:600}
.photo{max-width:320px;border-radius:4px;box-shadow:0 2px 10px rgba(0,0,0,.12);margin:6px 0 10px}
.slides img{width:100%;border:1px solid var(--line);border-radius:3px;display:block;margin-bottom:8px}
body.noslides .slides{display:none}
body.noslides .grid{grid-template-columns:1fr}
.tag{display:inline-block;font-size:11px;color:var(--muted);border:1px solid var(--line);
border-radius:10px;padding:1px 8px;margin:10px 6px 0 0}
"""


def _anchor(text: str) -> str:
    return "sec-" + re.sub(r"[^0-9a-zA-Z\u4e00-\u9fa5]+", "-", text)


def build_preview(spec: DeckSpec, out_path: str | Path, pdf: str | None = None,
                  title: str | None = None) -> Path:
    out = Path(out_path)
    images: dict[str, str] = {}
    crop_keys: dict[str, str] = {}

    if pdf:
        try:
            import pymupdf  # type: ignore
        except ImportError as exc:  # pragma: no cover
            raise SystemExit("生成带图预览需要 PyMuPDF：pip install pymupdf") from exc

        doc = pymupdf.open(pdf)
        try:
            pages = sorted({p for _, _, card in spec.iter_cards()
                            for p in (card.get("pages") or [])})
            for pno in pages:
                pix = doc[pno - 1].get_pixmap(dpi=80)
                images[f"p{pno}"] = base64.b64encode(
                    pix.tobytes("jpg", jpg_quality=60)).decode("ascii")
            used = {c["img"] for _, _, c in spec.iter_cards() if c.get("type") == "image"}
            z = 150 / 72.0
            for index, name in enumerate(sorted(used), 1):
                crop = spec.crops.get(name)
                if not crop:
                    continue
                page = doc[crop["page"] - 1]
                rect = pymupdf.Rect(*crop["rect"]) & page.rect
                pix = page.get_pixmap(matrix=pymupdf.Matrix(z, z), clip=rect)
                key = f"c{index}"
                crop_keys[name] = key
                images[key] = base64.b64encode(
                    pix.tobytes("jpg", jpg_quality=72)).decode("ascii")
        finally:
            doc.close()

    parts = [
        '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        f"<title>{html.escape(title or spec.name)} · 卡片预览</title>",
        f"<style>{_CSS}</style></head><body>",
        f"<header><h1>{html.escape(title or spec.name)}</h1>",
        f"<p>{spec.card_count} 张卡片 · {len(spec.sections)} 个子牌组"
        f"{' · 含原文截图' if images else ' · 未提供 PDF，仅文字'}</p></header>",
        '<nav id="top">',
    ]
    for sec in spec.sections:
        parts.append(
            f'<a href="#{_anchor(sec["deck"])}">{html.escape(sec["deck"])} · '
            f'{len(sec["cards"])} 张</a>')
    parts.append('<button id="toggle-slides">隐藏原文截图</button></nav><main>')

    for sec in spec.sections:
        parts.append(
            f'<section id="{_anchor(sec["deck"])}"><h2>{html.escape(sec["deck"])}'
            f'<small>{len(sec["cards"])} 张</small></h2>')
        for card in sec["cards"]:
            ctype = card.get("type", "qa")
            card_pages = card.get("pages") or []
            src = spec.location_label(card)
            slides = "".join(f'<img class="pg" data-k="p{p}" alt="原文 P{p}">'
                             for p in card_pages)
            badge = {"image": " · 图片题", "cloze": " · 填空"}.get(ctype, "")
            if ctype == "image":
                img_name = str(card.get("img", ""))
                key = crop_keys.get(img_name, "")
                photo = (f'<img class="photo" data-k="{html.escape(key, quote=True)}" '
                         f'alt="{html.escape(img_name, quote=True)}">') if key else ""
                question, answer = html.escape(card["q"]), sanitize_html(card["a"])
            elif ctype == "cloze":
                photo = ""
                question, answer = sanitize_html(card["text"]), sanitize_html(card.get("extra", ""))
            else:
                photo = ""
                question, answer = html.escape(card["q"]), sanitize_html(card["a"])
            tags = "".join(f'<span class="tag">{html.escape(t)}</span>'
                           for t in card.get("tags", []))
            parts.append(
                f'<div class="card"><div class="kicker">{html.escape(sec["deck"])} · {src}{badge}</div>'
                f'<div class="grid"><div><div class="q">{question}</div>'
                f'<div class="a">{answer}</div>{photo}</div>'
                f'<div class="slides">{slides}</div></div>'
                f'<div class="tags">{tags}</div></div>')
        parts.append("</section>")

    parts.append(
        "</main><script>\nconst IMG=" + json.dumps(images, ensure_ascii=False) + ";\n"
        "document.querySelectorAll('img[data-k]').forEach(function(el){"
        "var d=IMG[el.dataset.k]; if(d){el.src='data:image/jpeg;base64,'+d;}});\n"
        "var b=document.getElementById('toggle-slides');"
        "b.addEventListener('click',function(){document.body.classList.toggle('noslides');"
        "b.textContent=document.body.classList.contains('noslides')"
        "?'显示原文截图':'隐藏原文截图';});\n"
        "</script></body></html>"
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("".join(parts), encoding="utf-8")
    return out
