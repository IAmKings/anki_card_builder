#!/usr/bin/env python3
"""江诗丹顿 2023 VC Pocket Essential 培训手册 → Anki 卡组生成器。

从带图文的 PDF 培训手册中，把卡片内容（data/江斯丹顿/cards/*.json）
与手册页面截图、腕表产品图组合成 .apkg 卡组，同时导出单文件 HTML 预览。

用法:
    python3 generate_vc.py            # 生成 apkg + 预览
    python3 generate_vc.py --check    # 只校验卡片数据
    python3 generate_vc.py --no-preview

输出:
    output/江诗丹顿2023培训手册.apkg
    output/江诗丹顿2023培训手册_预览.html
"""

from __future__ import annotations

import argparse
import base64
import glob
import hashlib
import html
import json
import os
import re
import shutil
import sys
import time

import pymupdf

ROOT = os.path.dirname(os.path.abspath(__file__))
PDF_PATH = os.path.join(ROOT, "data", "江斯丹顿", "2023 VC Pocket Essential 培训手册.pdf")
CARD_DIR = os.path.join(ROOT, "data", "江斯丹顿", "cards")
CROP_PATH = os.path.join(ROOT, "data", "江斯丹顿", "crops.json")
OUT_DIR = os.path.join(ROOT, "output")
MEDIA_DIR = os.path.join(ROOT, ".work", "vc", "media")
APKG_PATH = os.path.join(OUT_DIR, "江诗丹顿2023培训手册.apkg")
PREVIEW_PATH = os.path.join(OUT_DIR, "江诗丹顿2023培训手册_预览.html")

PAGE_DPI = 170
PAGE_JPG_Q = 80
CROP_DPI = 300
CROP_JPG_Q = 88

DECK_ROOT = "江诗丹顿·2023培训手册"

MODEL_BASIC_ID = 1755010001
MODEL_CLOZE_ID = 1755010002

CSS = """
.card {
  font-family: "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", "Songti SC", serif;
  font-size: 19px;
  line-height: 1.65;
  color: #23201c;
  background: #fbf9f5;
  text-align: left;
  padding: 18px 20px 26px;
}
.kicker {
  font-size: 12px;
  letter-spacing: .12em;
  text-transform: uppercase;
  color: #9a7b4f;
  border-bottom: 1px solid #e3d8c4;
  padding-bottom: 6px;
  margin-bottom: 14px;
}
.q {
  font-size: 22px;
  font-weight: 600;
  line-height: 1.5;
  color: #1b1815;
}
.q .hint { display:block; font-weight:400; font-size:15px; color:#8a8378; margin-top:8px; }
.a { font-size: 19px; }
.a b, .a strong { color: #7a5c2e; }
.a ul, .a ol { margin: 8px 0 8px 4px; padding-left: 18px; }
.a li { margin: 3px 0; }
.a table { border-collapse: collapse; width: 100%; margin: 10px 0; font-size: 16px; }
.a th, .a td { border: 1px solid #e3d8c4; padding: 6px 9px; vertical-align: top; }
.a th { background: #f3ece0; font-weight: 600; }
.quote { border-left: 3px solid #c9b48b; padding-left: 12px; color: #4a443c; font-style: italic; }
.sep { border: 0; border-top: 1px solid #e3d8c4; margin: 18px 0 14px; }
.src {
  margin-top: 14px; font-size: 12.5px; color: #9a9285; letter-spacing: .04em;
}
.imgwrap { text-align: center; margin: 8px 0 16px; }
.imgwrap img.photo {
  max-width: 100%; max-height: 420px; border-radius: 4px;
  box-shadow: 0 2px 10px rgba(0,0,0,.12);
}
.pageimg { margin-top: 10px; text-align: center; }
.pageimg img.slide {
  max-width: 100%; border: 1px solid #e7ddcc; border-radius: 3px;
}
.cloze { color: #7a5c2e; font-weight: 600; }
hr#answer { border: 0; border-top: 1px solid #e3d8c4; margin: 14px 0; }
"""

BASIC_QFMT = """
<div class="wrap">
  <div class="kicker">江诗丹顿 · 2023 培训手册 · {{Source}}</div>
  {{#Image}}<div class="imgwrap">{{Image}}</div>{{/Image}}
  <div class="q">{{Front}}</div>
</div>
"""

BASIC_AFMT = """
<div class="wrap">
  <div class="kicker">江诗丹顿 · 2023 培训手册 · {{Source}}</div>
  <div class="a">{{Back}}</div>
  <hr class="sep">
  <div class="src">原文出处：《2023 VC Pocket Essential 培训手册》{{Source}}</div>
  {{#PageImage}}<div class="pageimg">{{PageImage}}</div>{{/PageImage}}
</div>
"""

CLOZE_QFMT = """
<div class="wrap">
  <div class="kicker">江诗丹顿 · 2023 培训手册 · {{Source}}</div>
  <div class="q" style="font-weight:400">{{cloze:Text}}</div>
</div>
"""

CLOZE_AFMT = """
<div class="wrap">
  <div class="kicker">江诗丹顿 · 2023 培训手册 · {{Source}}</div>
  <div class="a">{{cloze:Text}}<hr id="answer">{{Extra}}</div>
  <hr class="sep">
  <div class="src">原文出处：《2023 VC Pocket Essential 培训手册》{{Source}}</div>
  {{#PageImage}}<div class="pageimg">{{PageImage}}</div>{{/PageImage}}
</div>
"""


def log(msg: str) -> None:
    print(msg, flush=True)


# ---------------------------------------------------------------- data loading
def load_sections() -> list[dict]:
    files = sorted(glob.glob(os.path.join(CARD_DIR, "*.json")))
    if not files:
        raise SystemExit(f"没有找到卡片数据：{CARD_DIR}")
    sections = []
    for path in files:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        data["_file"] = os.path.basename(path)
        sections.append(data)
    return sections


def load_crops() -> dict[str, dict]:
    if not os.path.exists(CROP_PATH):
        return {}
    with open(CROP_PATH, encoding="utf-8") as fh:
        crops = json.load(fh)
    return {c["name"]: c for c in crops}


# ---------------------------------------------------------------- validation
ALLOWED_TYPES = {"qa", "image", "cloze"}


def validate(sections: list[dict], crops: dict[str, dict], page_count: int) -> list[str]:
    errors, warnings = [], []
    seen_front: dict[str, str] = {}
    total = 0
    for sec in sections:
        deck = sec.get("deck")
        if not deck:
            errors.append(f"{sec['_file']}: 缺少 deck 字段")
        for i, card in enumerate(sec.get("cards", []), 1):
            total += 1
            where = f"{sec['_file']}#{i}"
            ctype = card.get("type", "qa")
            if ctype not in ALLOWED_TYPES:
                errors.append(f"{where}: 未知 type={ctype}")
            if ctype == "cloze":
                text = card.get("text", "")
                if "{{c" not in text or "::" not in text:
                    errors.append(f"{where}: cloze 卡片缺少 {{{{c1::…}}}}")
                if not card.get("extra"):
                    warnings.append(f"{where}: cloze 缺少 extra")
                front = text
            else:
                if not card.get("q") or not card.get("a"):
                    errors.append(f"{where}: qa/image 卡片缺少 q 或 a")
                front = card.get("q", "")
            pages = card.get("pages") or []
            if not pages:
                errors.append(f"{where}: 缺少 pages（原文页码）")
            for p in pages:
                if not isinstance(p, int) or not (1 <= p <= page_count):
                    errors.append(f"{where}: 页码 {p!r} 超出 1-{page_count}")
            if ctype == "image":
                img = card.get("img")
                if not img:
                    errors.append(f"{where}: image 卡片缺少 img")
                elif img not in crops:
                    errors.append(f"{where}: img {img!r} 不在 crops.json 中")
            key = re.sub(r"\s+", "", front)[:80]
            if key in seen_front:
                warnings.append(f"{where}: 与 {seen_front[key]} 问题重复：{front[:30]}…")
            else:
                seen_front[key] = where
    log(f"共 {len(sections)} 个章节 / {total} 张卡片")
    return errors, warnings


# ---------------------------------------------------------------- media
def render_page_images(pages: set[int], doc: "pymupdf.Document") -> dict[int, str]:
    os.makedirs(MEDIA_DIR, exist_ok=True)
    names = {}
    for p in sorted(pages):
        name = f"vc-p{p:03d}.jpg"
        path = os.path.join(MEDIA_DIR, name)
        if not os.path.exists(path):
            page = doc[p - 1]
            pix = page.get_pixmap(dpi=PAGE_DPI)
            pix.save(path, jpg_quality=PAGE_JPG_Q)
        names[p] = name
    return names


def render_crops(crops: dict[str, dict], doc: "pymupdf.Document") -> dict[str, str]:
    os.makedirs(MEDIA_DIR, exist_ok=True)
    used = {}
    for name, spec in crops.items():
        page_no = spec["page"]
        rect = pymupdf.Rect(*spec["rect"])
        page = doc[page_no - 1]
        rect = rect & page.rect  # 防止超出页面
        z = CROP_DPI / 72.0
        path = os.path.join(MEDIA_DIR, f"{name}.jpg")
        if not os.path.exists(path):
            pix = page.get_pixmap(matrix=pymupdf.Matrix(z, z), clip=rect)
            pix.save(path, jpg_quality=CROP_JPG_Q)
        used[name] = f"{name}.jpg"
    return used


# ---------------------------------------------------------------- deck build
def build_deck(sections: list[dict], crops: dict[str, dict], page_names: dict[int, str],
               crop_names: dict[str, str], lite: bool = False
               ) -> tuple[object, list[str], dict[str, int]]:
    import genanki  # 延迟导入，--check 时无需安装

    basic = genanki.Model(
        MODEL_BASIC_ID,
        "江诗丹顿培训 · 问答",
        fields=[{"name": f} for f in ["Front", "Back", "Image", "Source", "PageImage"]],
        templates=[{"name": "问答卡", "qfmt": BASIC_QFMT, "afmt": BASIC_AFMT}],
        css=CSS,
    )
    cloze = genanki.Model(
        MODEL_CLOZE_ID,
        "江诗丹顿培训 · 填空",
        fields=[{"name": f} for f in ["Text", "Extra", "Source", "PageImage"]],
        templates=[{"name": "填空卡", "qfmt": CLOZE_QFMT, "afmt": CLOZE_AFMT}],
        css=CSS,
        model_type=genanki.Model.CLOZE,
    )

    decks, media, stats = [], set(), {}
    for si, sec in enumerate(sections):
        deck_name = f"{DECK_ROOT}::{sec['deck']}"
        deck = genanki.Deck(1755010100 + si, deck_name)
        count = 0
        for card in sec["cards"]:
            ctype = card.get("type", "qa")
            pages = card["pages"]
            src = "P" + "、P".join(str(p) for p in pages)
            if lite:
                page_imgs = ""
            else:
                page_imgs = "".join(
                    f'<img class="slide" src="{page_names[p]}">' for p in pages if p in page_names
                )
            page_html = f'<div class="pageimg">{page_imgs}</div>' if page_imgs else ""
            topic = sec["deck"]
            topic = topic.split(" ", 1)[1] if " " in topic else topic
            raw_tags = [topic] + [t for t in card.get("tags", [])]
            tags = list(dict.fromkeys(re.sub(r"\s+", "_", t) for t in raw_tags if t))

            if ctype == "cloze":
                fields = [card["text"], card.get("extra", ""), src, page_html]
                model = cloze
                guid_seed = f"{deck_name}|{card['text']}"
            else:
                front = card["q"]
                img_html = ""
                if ctype == "image":
                    img_html = f'<img class="photo" src="{crop_names[card["img"]]}">'
                fields = [front, card["a"], img_html, src, page_html]
                model = basic
                guid_seed = f"{deck_name}|{front}|{card['a']}"

            guid = hashlib.sha1(guid_seed.encode("utf-8")).hexdigest()[:12]
            note = genanki.Note(model=model, fields=fields, tags=tags, guid=guid)
            deck.add_note(note)
            count += 1
            if not lite:
                for p in pages:
                    if p in page_names:
                        media.add(page_names[p])
            if ctype == "image":
                media.add(crop_names[card["img"]])
        stats[deck_name] = count
        decks.append(deck)

    package = genanki.Package(decks)
    package.media_files = sorted(os.path.join(MEDIA_DIR, m) for m in media)
    return package, sorted(media), stats


# ---------------------------------------------------------------- preview
def img_to_b64(path: str) -> str:
    with open(path, "rb") as fh:
        return base64.b64encode(fh.read()).decode("ascii")


def build_preview(sections: list[dict], crops: dict[str, dict], doc, out_path: str) -> str:
    """生成单文件 HTML 预览。

    所有缩略图只以 base64 存一份，用 data-k 占位 + 脚本挂载，
    避免同一页截图在 272 张卡片里重复嵌入导致文件过大。
    """
    pages_used: list[int] = []
    crops_used: list[str] = []
    for sec in sections:
        for card in sec["cards"]:
            for pno in card["pages"]:
                if pno not in pages_used:
                    pages_used.append(pno)
            if card.get("type") == "image":
                crops_used.append(card["img"])

    images: dict[str, str] = {}
    for pno in sorted(pages_used):
        pix = doc[pno - 1].get_pixmap(dpi=80)
        images[f"p{pno}"] = base64.b64encode(pix.tobytes("jpg", jpg_quality=60)).decode("ascii")
    for name in dict.fromkeys(crops_used):
        spec = crops[name]
        page = doc[spec["page"] - 1]
        rect = pymupdf.Rect(*spec["rect"]) & page.rect
        z = 150 / 72.0
        pix = page.get_pixmap(matrix=pymupdf.Matrix(z, z), clip=rect)
        images["c" + name] = base64.b64encode(pix.tobytes("jpg", jpg_quality=72)).decode("ascii")

    parts = ["""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>江诗丹顿 2023 培训手册 · 卡片预览</title>
<style>
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
.quote{border-left:3px solid #c9b48b;padding-left:12px;font-style:italic;color:#4a443c}
.cloze{color:#7a5c2e;font-weight:600}
.photo{max-width:320px;border-radius:4px;box-shadow:0 2px 10px rgba(0,0,0,.12);margin:6px 0 10px}
.slides img{width:100%;border:1px solid var(--line);border-radius:3px;display:block;margin-bottom:8px}
body.noslides .slides{display:none}
body.noslides .grid{grid-template-columns:1fr}
.tag{display:inline-block;font-size:11px;color:var(--muted);border:1px solid var(--line);
border-radius:10px;padding:1px 8px;margin:10px 6px 0 0}
</style></head><body>
<header><h1>江诗丹顿 · 2023 VC Pocket Essential 培训手册</h1>
<p>Anki 卡片预览 · 品牌、历史、工艺、系列、机芯、钻石、保养与合规</p></header>
<nav id="top">"""]

    for sec in sections:
        anchor = "sec-" + re.sub(r"[^0-9a-zA-Z\u4e00-\u9fa5]+", "-", sec["deck"])
        parts.append(f'<a href="#{anchor}">{html.escape(sec["deck"])} · {len(sec["cards"])} 张</a>')
    parts.append('<button id="toggle-slides">隐藏原文截图</button></nav><main>')

    for sec in sections:
        anchor = "sec-" + re.sub(r"[^0-9a-zA-Z\u4e00-\u9fa5]+", "-", sec["deck"])
        parts.append(
            f'<section id="{anchor}"><h2>{html.escape(sec["deck"])}'
            f'<small>{len(sec["cards"])} 张</small></h2>'
        )
        for card in sec["cards"]:
            ctype = card.get("type", "qa")
            src = "P" + "、P".join(str(p) for p in card["pages"])
            slides = "".join(
                f'<img class="pg" data-k="p{p}" alt="原文 P{p}">' for p in card["pages"]
            )
            badge = " · 图片题" if ctype == "image" else (" · 填空" if ctype == "cloze" else "")
            if ctype == "image":
                photo = (
                    f'<img class="photo" data-k="c{card["img"]}" alt="{html.escape(card["img"])}">'
                )
                q = html.escape(card["q"])
                a = card["a"]
            elif ctype == "cloze":
                photo = ""
                q = card["text"]
                a = card.get("extra", "")
            else:
                photo = ""
                q = html.escape(card["q"])
                a = card["a"]
            tags = "".join(f'<span class="tag">{html.escape(t)}</span>' for t in card.get("tags", []))
            parts.append(
                f'<div class="card"><div class="kicker">{html.escape(sec["deck"])} · {src}{badge}</div>'
                f'<div class="grid"><div><div class="q">{q}</div><div class="a">{a}</div>{photo}</div>'
                f'<div class="slides">{slides}</div></div>'
                f'<div class="tags">{tags}</div></div>'
            )
        parts.append("</section>")

    parts.append(
        "</main><script>\nconst IMG=" + json.dumps(images, ensure_ascii=False) + ";\n"
        "document.querySelectorAll('img[data-k]').forEach(function(el){"
        "var d=IMG[el.dataset.k]; if(d){el.src='data:image/jpeg;base64,'+d;}});\n"
        "var b=document.getElementById('toggle-slides');"
        "b.addEventListener('click',function(){document.body.classList.toggle('noslides');"
        "b.textContent=document.body.classList.contains('noslides')?'显示原文截图':'隐藏原文截图';});\n"
        "</script></body></html>"
    )
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write("".join(parts))
    return out_path


# ---------------------------------------------------------------- main
def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="江诗丹顿培训手册 → Anki 卡组")
    ap.add_argument("--check", action="store_true", help="只校验卡片数据")
    ap.add_argument("--no-preview", action="store_true", help="不生成 HTML 预览")
    ap.add_argument("--lite", action="store_true", help="轻量版：不含原文页面截图（只保留图片题产品图）")
    ap.add_argument("--out", default=None, help="输出 .apkg 路径（默认 output/江诗丹顿2023培训手册.apkg）")
    args = ap.parse_args(argv)

    if not os.path.exists(PDF_PATH):
        log(f"找不到 PDF：{PDF_PATH}")
        return 1

    doc = pymupdf.open(PDF_PATH)
    page_count = doc.page_count
    sections = load_sections()
    crops = load_crops()

    errors, warnings = validate(sections, crops, page_count)
    for w in warnings:
        log(f"  ⚠ {w}")
    if errors:
        for e in errors:
            log(f"  ✗ {e}")
        log(f"校验失败：{len(errors)} 个错误")
        return 1
    log("校验通过")
    if args.check:
        return 0

    pages = {p for sec in sections for card in sec["cards"] for p in card["pages"]}
    if args.lite:
        log("轻量模式：跳过原文页面截图")
        page_names = {}
    else:
        log(f"渲染 {len(pages)} 张页面截图 …")
        page_names = render_page_images(pages, doc)

    used_crops = {c["img"] for sec in sections for c in sec["cards"] if c.get("type") == "image"}
    log(f"截取 {len(used_crops)} 张产品图 …")
    crop_names = render_crops(crops, doc)

    if os.path.exists(MEDIA_DIR):
        log(f"媒体目录：{MEDIA_DIR}")

    os.makedirs(OUT_DIR, exist_ok=True)
    out_apkg = args.out or APKG_PATH
    package, media, stats = build_deck(sections, crops, page_names, crop_names, lite=args.lite)
    package.write_to_file(out_apkg)
    size_mb = os.path.getsize(out_apkg) / 1024 / 1024
    log(f"已生成 {out_apkg}（{size_mb:.1f} MB，媒体 {len(media)} 个）")
    total = sum(stats.values())
    for name, count in stats.items():
        log(f"  {name}：{count} 张")
    log(f"合计 {total} 张卡片")

    if not args.no_preview:
        t0 = time.time()
        build_preview(sections, crops, doc, PREVIEW_PATH)
        psize = os.path.getsize(PREVIEW_PATH) / 1024 / 1024
        log(f"已生成预览 {PREVIEW_PATH}（{psize:.1f} MB，{time.time() - t0:.1f}s）")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
