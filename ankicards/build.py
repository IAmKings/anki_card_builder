"""从 DeckSpec 打包 .apkg：模型、模板、媒体、guid。

媒体命名规则（唯一真值）：
- 页面截图：<deck-slug>-p<page:03d>.jpg
- 产品裁图：<deck-slug>-<crop-name>.jpg
所有媒体名均为扁平 basename，不含路径与中文，避免 Anki/AnkiDroid 兼容问题。
"""

from __future__ import annotations

import hashlib
import re
import tempfile
from pathlib import Path

from .ids import deck_id, model_id
from .schema import DeckSpec

CSS = """
.card {
  font-family: "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", "Songti SC", serif;
  font-size: 19px; line-height: 1.65; color: #23201c; background: #fbf9f5;
  text-align: left; padding: 18px 20px 26px;
}
.kicker { font-size: 12px; letter-spacing: .12em; text-transform: uppercase; color: #9a7b4f;
  border-bottom: 1px solid #e3d8c4; padding-bottom: 6px; margin-bottom: 14px; }
.q { font-size: 22px; font-weight: 600; line-height: 1.5; color: #1b1815; }
.a { font-size: 19px; }
.a b, .a strong { color: #7a5c2e; }
.a ul, .a ol { margin: 8px 0 8px 4px; padding-left: 18px; }
.a li { margin: 3px 0; }
.a table { border-collapse: collapse; width: 100%; margin: 10px 0; font-size: 16px; }
.a th, .a td { border: 1px solid #e3d8c4; padding: 6px 9px; vertical-align: top; }
.a th { background: #f3ece0; font-weight: 600; }
.sep { border: 0; border-top: 1px solid #e3d8c4; margin: 18px 0 14px; }
.src { margin-top: 14px; font-size: 12.5px; color: #9a9285; letter-spacing: .04em; }
.imgwrap { text-align: center; margin: 8px 0 16px; }
.imgwrap img.photo { max-width: 100%; max-height: 420px; border-radius: 4px;
  box-shadow: 0 2px 10px rgba(0,0,0,.12); }
.pageimg { margin-top: 10px; text-align: center; }
.pageimg img.slide { max-width: 100%; border: 1px solid #e7ddcc; border-radius: 3px; }
.cloze { color: #7a5c2e; font-weight: 600; }
hr#answer { border: 0; border-top: 1px solid #e3d8c4; margin: 14px 0; }
"""

BASIC_QFMT = """
<div class="wrap">
  <div class="kicker">{{Source}}</div>
  {{#Image}}<div class="imgwrap">{{Image}}</div>{{/Image}}
  <div class="q">{{Front}}</div>
</div>
"""

BASIC_AFMT = """
<div class="wrap">
  <div class="kicker">{{Source}}</div>
  <div class="a">{{Back}}</div>
  <hr class="sep">
  <div class="src">原文出处：{{Source}}</div>
  {{#PageImage}}<div class="pageimg">{{PageImage}}</div>{{/PageImage}}
</div>
"""

CLOZE_QFMT = """
<div class="wrap">
  <div class="kicker">{{Source}}</div>
  <div class="q" style="font-weight:400">{{cloze:Text}}</div>
</div>
"""

CLOZE_AFMT = """
<div class="wrap">
  <div class="kicker">{{Source}}</div>
  <div class="a">{{cloze:Text}}<hr id="answer">{{Extra}}</div>
  <hr class="sep">
  <div class="src">原文出处：{{Source}}</div>
  {{#PageImage}}<div class="pageimg">{{PageImage}}</div>{{/PageImage}}
</div>
"""


def _tags(section: str, card: dict) -> list[str]:
    """Anki 标签不能含空格；章节名去掉序号后作为顶层标签。"""
    topic = section.split(" ", 1)[1] if " " in section else section
    raw = [topic] + list(card.get("tags", []) or [])
    out: list[str] = []
    for tag in raw:
        cleaned = re.sub(r"\s+", "_", str(tag)).strip()
        if cleaned and cleaned not in out:
            out.append(cleaned)
    return out


def deck_slug(name: str) -> str:
    return hashlib.sha1(name.encode("utf-8")).hexdigest()[:6]


def _import_pymupdf():
    try:
        import pymupdf  # type: ignore
    except ImportError as exc:  # pragma: no cover - 取决于环境
        raise SystemExit(
            "需要 PyMuPDF 才能渲染页面/裁图：pip install pymupdf\n"
            "（渲染是可选能力，纯文本牌组不需要它）"
        ) from exc
    return pymupdf


def _render(pdf_path: str, pages: set[int], crops: dict[str, dict], media_dir: Path,
            slug: str, lite: bool, page_dpi: int, crop_dpi: int, quality: int
            ) -> dict[str, str]:
    """渲染页面截图与裁图，返回 crop_name -> 媒体文件名。"""
    pymupdf = _import_pymupdf()
    doc = pymupdf.open(pdf_path)
    try:
        if not lite:
            for pno in sorted(pages):
                out = media_dir / f"{slug}-p{pno:03d}.jpg"
                if not out.exists():
                    doc[pno - 1].get_pixmap(dpi=page_dpi).save(str(out), jpg_quality=quality)
        names: dict[str, str] = {}
        z = crop_dpi / 72.0
        for name, spec in crops.items():
            page = doc[spec["page"] - 1]
            rect = pymupdf.Rect(*spec["rect"]) & page.rect
            out = media_dir / f"{slug}-{name}.jpg"
            if not out.exists():
                page.get_pixmap(matrix=pymupdf.Matrix(z, z), clip=rect).save(
                    str(out), jpg_quality=quality)
            names[name] = out.name
        return names
    finally:
        doc.close()


def build(spec: DeckSpec, out_path: str | Path, pdf: str | None = None, lite: bool = False,
          page_dpi: int = 170, crop_dpi: int = 300, quality: int = 80) -> dict:
    import genanki  # 延迟导入：--check 不需要它

    slug = deck_slug(spec.name)
    pages: set[int] = {p for _, _, card in spec.iter_cards()
                       for p in card.get("pages") or [] if isinstance(p, int)}
    used_crops = {card["img"] for _, _, card in spec.iter_cards()
                  if card.get("type") == "image" and card.get("img")}
    crops = {k: v for k, v in spec.crops.items() if k in used_crops}

    if used_crops and not pdf:
        raise SystemExit(
            f"这个牌组有 {len(used_crops)} 张图片题，必须提供 --pdf 才能裁图；"
            "或先去掉图片题再构建。"
        )

    stats = {"notes": 0, "media": 0, "decks": 0}
    with tempfile.TemporaryDirectory(prefix="ankicards-") as tmp:
        media_dir = Path(tmp)
        crop_names: dict[str, str] = {}
        if pdf:
            crop_names = _render(pdf, pages, crops, media_dir, slug, lite,
                                 page_dpi, crop_dpi, quality)
        elif pages and not lite:
            print("⚠ 未提供 --pdf：不生成原文页截图（等同于 --lite）")

        basic = genanki.Model(
            model_id(spec.name, "basic"),
            f"{spec.name} · 问答",
            fields=[{"name": n} for n in ["Front", "Back", "Image", "Source", "PageImage"]],
            templates=[{"name": "问答卡", "qfmt": BASIC_QFMT, "afmt": BASIC_AFMT}],
            css=CSS,
        )
        cloze = genanki.Model(
            model_id(spec.name, "cloze"),
            f"{spec.name} · 填空",
            fields=[{"name": n} for n in ["Text", "Extra", "Source", "PageImage"]],
            templates=[{"name": "填空卡", "qfmt": CLOZE_QFMT, "afmt": CLOZE_AFMT}],
            css=CSS,
            model_type=genanki.Model.CLOZE,
        )

        decks, media = [], set()
        for sec in spec.sections:
            full_name = f"{spec.name}::{sec['deck']}" if sec["deck"] else spec.name
            deck = genanki.Deck(deck_id(full_name), full_name)
            for card in sec["cards"]:
                ctype = card.get("type", "qa")
                pages_src = "P" + "、P".join(str(p) for p in card["pages"])
                page_imgs = ""
                if not lite and pdf:
                    page_imgs = "".join(
                        f'<img class="slide" src="{slug}-p{p:03d}.jpg">'
                        for p in card["pages"] if p in pages
                    )
                page_html = f'<div class="pageimg">{page_imgs}</div>' if page_imgs else ""
                if not lite and pdf:
                    media.update(f"{slug}-p{p:03d}.jpg" for p in card["pages"] if p in pages)

                if ctype == "cloze":
                    fields = [card["text"], card.get("extra", ""), pages_src, page_html]
                    model, seed = cloze, f"{full_name}|{card['text']}"
                else:
                    img_html = ""
                    if ctype == "image":
                        fname = crop_names.get(card["img"], "")
                        if not fname:
                            raise SystemExit(f"裁图失败: {card['img']}")
                        img_html = f'<img class="photo" src="{fname}">'
                        media.add(fname)
                    fields = [card["q"], card["a"], img_html, pages_src, page_html]
                    model, seed = basic, f"{full_name}|{card['q']}|{card['a']}"

                guid = hashlib.sha1(seed.encode("utf-8")).hexdigest()[:12]
                deck.add_note(genanki.Note(model=model, fields=fields,
                                           tags=_tags(sec["deck"], card), guid=guid))
                stats["notes"] += 1
            decks.append(deck)
            stats["decks"] += 1

        package = genanki.Package(decks)
        if media:
            package.media_files = sorted(str(media_dir / m) for m in media)
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        package.write_to_file(str(out_path))
        stats["media"] = len(media)
        stats["bytes"] = out_path.stat().st_size
        stats["path"] = str(out_path)
        return stats
