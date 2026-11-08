"""卡片数据契约：加载、校验。

一个 deck 目录的形状：

    <deck>/
      deck.json          # 可选：{"name": "顶层牌组名", "source_kind": "pdf"}
      cards/*.json       # 必需：每个文件 {"deck": "子牌组名", "cards": [...]}
      crops.json         # 可选：图片题的裁图区域

定位语义（唯一真值）：
  pages  —— 只表示 **PDF 页码**，用于背面截图与裁图。
            来源为 md/txt/docx/image 时用 pages 直接报错；
            来源未声明（unknown）时兼容放行，但整副牌组只给 1 条 warning。
  source —— 非 PDF 来源的溯源字符串（文件名 > 章节 > 段落/表格 id），任意来源都可用。
  两者可以并存：pages 给截图，source 给段落级定位。

卡片字段（白名单，未知字段直接报错）：
  type: qa | image | cloze
  q / a: 问答与图片题的正面/背面
  text / extra: 填空题的正文（含 {{c1::…}}）与补充
  pages: list[int]，PDF 页码，可省略
  source: str，溯源说明，可省略（与 pages 至少给一个）
  tags: list[str]，可选
  img: 图片题正面图的 crop 名，必须在 crops.json 中存在
"""

from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from .errors import CardError

CARD_TYPES = {"qa", "image", "cloze"}
SOURCE_KINDS = {"pdf", "docx", "md", "txt", "image", "unknown"}
# pages 只表示 PDF 页码；unknown 为兼容未声明 source_kind 的历史牌组而放行（仅 warning）。
PAGES_ALLOWED = {"pdf", "unknown"}
CARD_FIELDS = {"type", "q", "a", "text", "extra", "pages", "source", "tags", "img"}



@dataclass
class Report:
    """校验/验证结果。errors 非空即失败。"""

    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    def add_error(self, where: str, msg: str) -> None:
        self.errors.append(f"{where}: {msg}" if where else msg)

    def add_warning(self, where: str, msg: str) -> None:
        self.warnings.append(f"{where}: {msg}" if where else msg)


@dataclass
class DeckSpec:
    root: Path
    name: str
    sections: list[dict]              # [{"file": str, "deck": str, "cards": list[dict]}]
    crops: dict[str, dict]            # name -> {"page": int, "rect": [x0,y0,x1,y1]}
    source_kind: str = "unknown"

    @property
    def card_count(self) -> int:
        return sum(len(s["cards"]) for s in self.sections)

    @property
    def has_pages(self) -> bool:
        return any(card.get("pages") for _, _, card in self.iter_cards())

    def iter_cards(self):
        for sec in self.sections:
            for idx, card in enumerate(sec["cards"], 1):
                yield sec, idx, card


def load_json(path: Path) -> dict | list:
    """读取并解析 JSON；坏文件给出可读错误与退出码 2，而不是 traceback。"""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:  # UnicodeDecodeError 也是 ValueError
        raise CardError(f"{path} 不是合法的 UTF-8 JSON: {exc}") from exc


def load_spec(deck_dir: str | Path, name: str | None = None) -> DeckSpec:
    root = Path(deck_dir).expanduser().resolve()
    if not root.is_dir():
        raise CardError(f"不是目录: {root}")

    manifest = root / "deck.json"
    manifest_name = ""
    manifest_kind = "unknown"
    if manifest.exists():
        data = load_json(manifest)
        if not isinstance(data, dict):
            raise CardError(f"{manifest} 必须是 JSON 对象")
        manifest_name = str(data.get("name", "")).strip()
        manifest_kind = str(data.get("source_kind", "unknown")).strip() or "unknown"

    card_files = sorted((root / "cards").glob("*.json")) if (root / "cards").is_dir() else []
    if not card_files:
        raise CardError(f"找不到卡片数据: {root}/cards/*.json")

    sections = []
    for path in card_files:
        data = load_json(path)
        if not isinstance(data, dict):
            raise CardError(f"{path} 必须是 JSON 对象")
        cards = data.get("cards")
        if not isinstance(cards, list) or not all(isinstance(c, dict) for c in cards):
            raise CardError(f"{path}: cards 必须是对象数组")
        sections.append(
            {
                "file": path.name,
                "deck": str(data.get("deck", "")).strip(),
                "cards": cards,
            }
        )

    crops_path = root / "crops.json"
    crops = {}
    if crops_path.exists():
        raw = load_json(crops_path)
        if isinstance(raw, list):
            if not all(isinstance(c, dict) and c.get("name") for c in raw):
                raise CardError(f"{crops_path}: 数组元素必须是含 name 的对象")
            crops = {c["name"]: c for c in raw}
        elif isinstance(raw, dict):
            if not all(isinstance(v, dict) for v in raw.values()):
                raise CardError(f"{crops_path}: 每个裁图值必须是对象")
            crops = raw
        else:
            raise CardError(f"{crops_path}: 必须是对象或数组")

    return DeckSpec(
        root=root,
        name=(name or manifest_name or root.name),
        sections=sections,
        crops=crops,
        source_kind=manifest_kind,
    )


def _norm(text: str) -> str:
    return re.sub(r"\s+", "", text or "")


def location_label(card: dict) -> str:
    """卡片背面的溯源行：PDF 页码 + source，统一转义，build 与 preview 共用。"""
    pages = card.get("pages") or []
    page_label = ("P" + "、P".join(str(p) for p in pages)) if pages else ""
    source_label = str(card.get("source", "")).strip()
    return html.escape(" · ".join(x for x in (page_label, source_label) if x))


def card_identity(card: dict) -> tuple:
    """「什么算同一张卡」的唯一真值：schema 查重与 build guid 都用它。

    qa    -> (q, a)          同题干不同答案不算重复
    image -> (img, q, a)     同题干同答案但不同图也不算重复
    cloze -> (text,)         cloze 的答案是隐藏的，文本即身份
    """
    ctype = card.get("type", "qa")
    if ctype == "image":
        return ("image", str(card.get("img", "")), _norm(card.get("q", "")), _norm(card.get("a", "")))
    if ctype == "cloze":
        return ("cloze", _norm(card.get("text", "")))
    return ("qa", _norm(card.get("q", "")), _norm(card.get("a", "")))


def identity_seed(deck_name: str, card: dict) -> str:
    """guid 种子的唯一实现：牌组名 + 结构化身份。算法变更需同步改黄金测试。"""
    return f"{deck_name}|{json.dumps(card_identity(card), ensure_ascii=False)}"


def validate(spec: DeckSpec, page_count: int | None = None,
             page_size: tuple[float, float] | None = None,
             ingest: dict[int, str] | None = None) -> Report:
    """校验卡片契约。

    page_count / page_size：能拿到源 PDF 时才传，用于页码上界与裁图越界。
    ingest：ingest 产物（page -> 文本）。传入时启用**溯源闸门**：
            卡片引用的每一页都必须存在且该页文本非空。
    """
    rep = Report()
    seen_sections: dict[str, str] = {}
    seen_identity: dict[tuple, str] = {}
    used_crops: set[str] = set()
    kind = spec.source_kind

    if not spec.name.strip():
        rep.add_error("", "deck 名称为空")
    if kind not in SOURCE_KINDS:
        rep.add_error("deck.json", f"source_kind 非法: {kind!r}（可选 {sorted(SOURCE_KINDS)}）")
    if kind == "unknown" and spec.card_count:
        choices = "、".join(sorted(SOURCE_KINDS - {"unknown"}))
        rep.add_warning("deck.json", f"未声明 source_kind（可选 {choices}），按 unknown 处理")

    pages_without_text: list[int] = []
    if ingest is not None:
        pages_without_text = sorted(p for p, text in ingest.items() if not (text or "").strip())

    for sec in spec.sections:
        sec_name = sec["deck"]
        where_sec = sec["file"]
        if not sec_name:
            rep.add_error(where_sec, "缺少 deck 字段")
        if sec_name in seen_sections:
            rep.add_error(where_sec, f"子牌组重名: {sec_name}（另见 {seen_sections[sec_name]}）")
        seen_sections.setdefault(sec_name, where_sec)

        for idx, card in enumerate(sec["cards"], 1):
            where = f"{where_sec}#{idx}"
            unknown = set(card) - CARD_FIELDS
            if unknown:
                rep.add_error(where, f"未知字段: {sorted(unknown)}（白名单之外的字段不会被构建）")

            ctype = card.get("type", "qa")
            if not isinstance(ctype, str) or ctype not in CARD_TYPES:
                rep.add_error(where, f"未知 type={ctype!r}")
                continue
            bad_types = [k for k in ("q", "a", "text", "extra", "source")
                         if k in card and not isinstance(card[k], str)]
            if bad_types:
                rep.add_error(where, f"字段类型错误: {', '.join(bad_types)} 必须是字符串")
                continue

            if ctype in ("qa", "image"):
                if not str(card.get("q", "")).strip():
                    rep.add_error(where, "缺少 q")
                if not str(card.get("a", "")).strip():
                    rep.add_error(where, "缺少 a")
            else:  # cloze
                text = str(card.get("text", ""))
                if "{{c" not in text or "::" not in text:
                    rep.add_error(where, "cloze 缺少 {{c1::…}}")
                if not str(card.get("extra", "")).strip():
                    rep.add_warning(where, "cloze 缺少 extra")

            pages = card.get("pages")
            source = str(card.get("source", "")).strip()
            if pages is None and not source:
                rep.add_warning(where, "缺少 pages 与 source（无法溯源到原文）")

            if pages is not None:
                if kind not in PAGES_ALLOWED:
                    rep.add_error(where, f"source_kind={kind} 的来源不能用 pages（pages 仅表示 PDF 页）")
                if not isinstance(pages, list) or not pages:
                    rep.add_error(where, "pages 必须是非空数组（或用 source 溯源）")
                else:
                    for p in pages:
                        if not isinstance(p, int) or p < 1:
                            rep.add_error(where, f"页码非法: {p!r}")
                        elif page_count is not None and p > page_count:
                            rep.add_error(where, f"页码 {p} 超出 1-{page_count}")
                        elif ingest is not None:
                            if p not in ingest:
                                rep.add_error(where, f"页码 {p} 不在 ingest 产物中")
                            elif p in pages_without_text:
                                rep.add_error(where, f"页码 {p} 在 ingest 产物中没有文本（可能是空页）")

            tags = card.get("tags", [])
            if tags and not (isinstance(tags, list) and all(isinstance(t, str) for t in tags)):
                rep.add_error(where, "tags 必须是字符串数组")

            if ctype == "image":
                img = card.get("img")
                if not img:
                    rep.add_error(where, "图片题缺少 img")
                elif img not in spec.crops:
                    rep.add_error(where, f"img {img!r} 不在 crops.json 中")
                else:
                    used_crops.add(img)

            ident = card_identity(card)
            if ident in seen_identity:
                rep.add_warning(where, f"与 {seen_identity[ident]} 身份重复（同类型且同内容）")
            else:
                seen_identity[ident] = where

    for crop_name, crop in spec.crops.items():
        where = f"crops:{crop_name}"
        page = crop.get("page")
        rect = crop.get("rect")
        if not isinstance(page, int) or page < 1:
            rep.add_error(where, f"page 非法: {page!r}")
        elif page_count is not None and page > page_count:
            rep.add_error(where, f"page {page} 超出 1-{page_count}")
        if not (isinstance(rect, list) and len(rect) == 4
                and all(isinstance(v, (int, float)) for v in rect)):
            rep.add_error(where, "rect 必须是 [x0,y0,x1,y1] 四个数字")
            continue
        x0, y0, x1, y1 = rect
        if not (x0 < x1 and y0 < y1):
            rep.add_error(where, f"rect 顺序非法: {rect}")
        if page_size:
            pw, ph = page_size
            if not (0 <= x0 < pw and 0 <= x1 <= pw and 0 <= y0 < ph and 0 <= y1 <= ph):
                rep.add_error(where, f"rect 超出页面 {pw}x{ph}: {rect}")
        if crop_name not in used_crops:
            rep.add_warning(where, "裁图未被任何图片题引用")

    if spec.card_count == 0:
        rep.add_error("", "卡片数量为 0")

    return rep
