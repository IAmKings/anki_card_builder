"""导出后结构审计：把 .apkg 解开，检查「能不能被 Anki 正常导入」。

检查项（全部只读）：孤儿卡片、无卡笔记、重复 guid、字段数不匹配、空必填字段、
HTML 未闭合、残留模板标记、媒体引用缺失/多余、卡组父子关系、card.ord 越界、
正面疑似泄露答案。
"""

from __future__ import annotations

import collections
import json
import re
import sqlite3
import tempfile
import zipfile
from html.parser import HTMLParser
from pathlib import Path

VOID = {"br", "img", "hr", "input", "meta", "link", "col", "area", "base", "source", "wbr"}
OPTIONAL_END = {"li", "p", "td", "th", "tr", "thead", "tbody", "option"}
REQUIRED_NAMES = ("Front", "Back", "Text")


class _HtmlChecker(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: list[tuple[str, tuple[int, int]]] = []
        self.errors: list[str] = []

    def _ctx(self) -> str:
        return "/".join(t for t, _ in self.stack[-4:]) or "root"

    def handle_starttag(self, tag, attrs):
        if tag in VOID:
            return
        if tag in ("td", "th") and not any(t in ("table", "tr") for t, _ in self.stack):
            self.errors.append(f"<{tag}> 出现在表格之外")
        if tag == "tr":
            if not any(t == "table" for t, _ in self.stack):
                self.errors.append("<tr> 出现在 <table> 之外")
            if self.stack and self.stack[-1][0] in ("td", "th"):
                self.errors.append("<tr> 前一个单元格未闭合")
        if tag == "li" and self.stack and self.stack[-1][0] == "li":
            self.stack.pop()
        if tag in ("td", "th"):
            while self.stack and self.stack[-1][0] in ("td", "th"):
                self.stack.pop()
        self.stack.append((tag, self.getpos()))

    def handle_startendtag(self, tag, attrs):
        pass

    def handle_endtag(self, tag):
        if tag in VOID:
            return
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                for t, _ in self.stack[i + 1:]:
                    if t not in OPTIONAL_END:
                        self.errors.append(f"<{t}> 未闭合（在 </{tag}> 前）")
                del self.stack[i:]
                return
        self.errors.append(f"</{tag}> 没有对应的开始标签（{self._ctx()}）")

    def result(self) -> list[str]:
        for t, _ in self.stack:
            if t not in OPTIONAL_END:
                self.errors.append(f"<{t}> 到结尾仍未闭合")
        return self.errors


def check_html(text: str) -> list[str]:
    checker = _HtmlChecker()
    try:
        checker.feed(text)
        checker.close()
    except Exception as exc:  # noqa: BLE001 - 畸形 HTML 不该让审计崩掉
        return [f"解析异常: {exc}"]
    return checker.result()


def _open_collection(root: Path) -> sqlite3.Connection:
    for name in ("collection.anki21", "collection.anki2", "collection.anki21b"):
        path = root / name
        if path.exists():
            return sqlite3.connect(str(path))
    raise SystemExit(f"apkg 里找不到 collection 数据库: {sorted(p.name for p in root.iterdir())}")


def verify(apkg: str | Path) -> dict:
    apkg = Path(apkg)
    errors: list[str] = []
    warnings: list[str] = []

    with tempfile.TemporaryDirectory(prefix="ankicards-verify-") as tmp:
        root = Path(tmp)
        with zipfile.ZipFile(apkg) as archive:
            bad = archive.testzip()
            if bad is not None:
                errors.append(f"zip 校验失败，损坏条目: {bad}")
            archive.extractall(root)

        media_path = root / "media"
        media = json.loads(media_path.read_text(encoding="utf-8")) if media_path.exists() else {}
        media_names = set(media.values())

        con = _open_collection(root)
        con.text_factory = str
        cur = con.cursor()
        models_raw, decks_raw, conf_raw = cur.execute("select models,decks,conf from col").fetchone()
        models = {str(k): v for k, v in json.loads(models_raw).items()}
        decks = {int(k): v for k, v in json.loads(decks_raw).items()}
        conf = json.loads(conf_raw)
        fields = {mid: [f["name"] for f in m["flds"]] for mid, m in models.items()}
        templates = {mid: m["tmpls"] for mid, m in models.items()}

        def _rendered(mid: str) -> set[str]:
            """模板里真正会渲染的字段；Source/Section 这类元数据不参与 HTML 检查。"""
            names: set[str] = set()
            for tmpl in templates[mid]:
                for ref in re.findall(r"\{\{[#/]?([^{}]+)\}\}", tmpl.get("qfmt", "") + tmpl.get("afmt", "")):
                    ref = ref.strip()
                    for prefix in ("cloze:", "type:", "hint:"):
                        if ref.startswith(prefix):
                            ref = ref[len(prefix):]
                    names.add(ref)
            return names

        notes = cur.execute("select id,guid,mid,flds,sfld from notes").fetchall()
        cards = cur.execute("select id,nid,did,ord from cards").fetchall()

        # --- 卡组
        deck_names = collections.Counter(d["name"] for d in decks.values())
        for name, count in deck_names.items():
            if not name:
                errors.append("存在无名称卡组")
            if count > 1:
                errors.append(f"卡组重名 x{count}: {name}")
        for deck in decks.values():
            if "::" in deck["name"]:
                parent = deck["name"].rsplit("::", 1)[0]
                if parent not in deck_names:
                    warnings.append(f"父卡组未单独存在（Anki 导入时自动创建）: {parent}")

        # --- 笔记
        note_ids = {n[0] for n in notes}
        card_nids = {c[1] for c in cards}
        orphans = [c for c in cards if c[1] not in note_ids]
        if orphans:
            errors.append(f"孤儿卡片 {len(orphans)} 张（指向不存在的笔记）")
        without_card = note_ids - card_nids
        if without_card:
            warnings.append(f"{len(without_card)} 条笔记没有卡片（cloze 全被删时会这样）")

        guids = collections.Counter(n[1] for n in notes)
        dup_guids = [g for g, c in guids.items() if c > 1]
        if dup_guids:
            errors.append(f"重复 guid {len(dup_guids)} 组")

        img_refs: collections.Counter[str] = collections.Counter()
        empty_required: list[str] = []
        bad_html: list[str] = []
        mustache: list[str] = []
        ctrl: list[str] = []
        leaks: list[str] = []
        field_count_bad: list[str] = []

        for nid, guid, mid, raw, sfld in notes:
            mid = str(mid)
            names = fields[mid]
            values = raw.split("\x1f")
            if len(values) != len(names):
                field_count_bad.append(f"note {nid}: {len(values)} 个字段 != 模型 {len(names)}")
                continue
            row = dict(zip(names, values))
            rendered = _rendered(mid)
            required = [n for n in REQUIRED_NAMES if n in names and n in rendered]
            for name in required:
                if name in ("Front", "Text", "Back") and not row[name].strip():
                    empty_required.append(f"note {nid}.{name} 为空")
            is_cloze = models[mid].get("type") == 1
            for name, value in row.items():
                if name not in rendered:
                    continue
                if "\x1f" in value:
                    ctrl.append(f"note {nid}.{name}")
                if "{{" in value and not (is_cloze and name == "Text"):
                    mustache.append(f"note {nid}.{name}: {value[:40]}")
                for src in re.findall(r'<img[^>]+src="([^"]+)"', value or ""):
                    img_refs[src] += 1
                if re.search(r"\\[<>]", value or ""):
                    warnings.append(f"note {nid}.{name}: 含 markdown 转义残留（\\< / \\>）")
                html_value = re.sub(r"\\([<>])", lambda m: "&lt;" if m.group(1) == "<" else "&gt;", value or "")
                errs = check_html(html_value)
                if errs:
                    bad_html.append(f"note {nid}.{name}: {errs[0]}")
            front = row.get("Front") or row.get("Text") or ""
            if models[mid].get("type") != 1 and re.search(r"答案[：:]", front):
                leaks.append(f"note {nid}: front 含“答案：”")
            back = row.get("Back") or ""
            plain_front = re.sub(r"\s+", "", re.sub(r"<[^>]+>", "", front))
            plain_back = re.sub(r"\s+", "", re.sub(r"<[^>]+>", "", back))
            if len(plain_back) > 20 and plain_back[:40] and plain_back[:40] in plain_front:
                leaks.append(f"note {nid}: 答案开头出现在正面")

        if field_count_bad:
            errors.extend(field_count_bad[:5])
        if empty_required:
            errors.extend(empty_required[:5])
        if bad_html:
            errors.extend(bad_html[:5])
        if mustache:
            errors.extend(mustache[:5])
        if ctrl:
            errors.extend(ctrl[:5])
        if leaks:
            warnings.extend(leaks[:5])

        missing = sorted(set(img_refs) - media_names)
        unused = sorted(media_names - set(img_refs))
        if missing:
            errors.append(f"缺失媒体 {len(missing)} 个: {missing[:5]}")
        if unused:
            warnings.append(f"未被引用的媒体 {len(unused)} 个: {unused[:5]}")

        ord_bad = []
        for cid, nid, did, ordv in cards:
            note = next((n for n in notes if n[0] == nid), None)
            if note is None:
                continue
            if models[str(note[2])].get("type") == 1:
                continue  # cloze 的 ord 是删除序号，不按模板数校验
            if ordv >= len(templates[str(note[2])]):
                ord_bad.append(f"card {cid}: ord={ordv} 超出模板数")
        if ord_bad:
            errors.extend(ord_bad[:5])

        per_deck: dict[str, int] = {}
        name_by_did = {did: d["name"] for did, d in decks.items()}
        for _, _, did, _ in cards:
            per_deck[name_by_did.get(did, str(did))] = per_deck.get(name_by_did.get(did, str(did)), 0) + 1

        return {
            "apkg": str(apkg),
            "size_bytes": apkg.stat().st_size,
            "notes": len(notes),
            "cards": len(cards),
            "models": len(models),
            "decks": len(decks),
            "media_entries": len(media),
            "img_refs_total": sum(img_refs.values()),
            "per_deck_cards": per_deck,
            "note_types": {models[m]["name"]: c for m, c in collections.Counter(str(n[2]) for n in notes).items()},
            "field_counts": {models[m]["name"]: len(f) for m, f in fields.items()},
            "conf": {k: conf.get(k) for k in ("nextPos", "curDeck", "newSpread", "activeDecks")},
            "errors": errors,
            "warnings": list(dict.fromkeys(warnings)),
        }
