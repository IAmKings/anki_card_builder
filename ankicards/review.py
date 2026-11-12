"""派生题的人工复核页：单文件 HTML，无外部依赖、不上传任何内容。

用法（CLI）：python3 -m ankicards derive review <plan.json> --deck <牌组目录> --out <out.html>
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from .derive import load_derived_plan, plain, source_key
from .schema import load_spec

SUSPICIOUS_RATIO = 1.8


def _norm(text: str) -> str:
    return re.sub(r"\s+", "", plain(text or ""))


def _ratio(entry: dict) -> float:
    options = entry.get("options") or []
    lengths = [len((o.get("text") or "").strip()) for o in options]
    lengths = [n for n in lengths if n]
    if len(lengths) < 2:
        return 0.0
    return round(max(lengths) / max(1, min(lengths)), 2)


def _masked(text: str) -> str:
    match = re.search(r"\{\{c1::(.*?)\}\}", text or "")
    return match.group(1).strip() if match else ""


def _source_map(spec) -> dict:
    out = {}
    for section in spec.sections:
        name = section.get("deck") or ""
        for card in section.get("cards") or []:
            key = source_key(name, spec.name, card)
            out[key] = {
                "section": name,
                "q": plain(card.get("q") or card.get("text") or ""),
                "a": plain(card.get("a") or card.get("extra") or ""),
                "locator": card.get("source") or "",
                "pages": card.get("pages") or [],
                "tags": card.get("tags") or [],
            }
    return out


def _flags(entry: dict, source: dict | None) -> list[dict]:
    flags = []
    kind = entry.get("type")
    if source is None:
        flags.append({"level": "bad", "text": "源卡不在牌组里"})
    if kind == "choice":
        ratio = _ratio(entry)
        if ratio > 2.0:
            flags.append({"level": "bad", "text": f"选项长度比 {ratio}（>2）"})
        elif ratio > SUSPICIOUS_RATIO:
            flags.append({"level": "warn", "text": f"选项长度比 {ratio}（偏斜）"})
        opts = [re.sub(r"\s+", "", (o.get("text") or "")) for o in entry.get("options") or []]
        dup = [o for o in set(opts) if opts.count(o) > 1]
        if dup:
            flags.append({"level": "bad", "text": f"重复选项 {len(dup)} 个"})
        answer = (entry.get("options") or [{}] * 0)[0] if False else None
        idx = entry.get("answer_index")
        if isinstance(idx, int) and 0 <= idx < len(entry.get("options") or []):
            correct = (entry["options"][idx].get("text") or "").strip()
            if len(correct) < 8:
                flags.append({"level": "warn", "text": "正确项过短"})
        if (entry.get("stem") or "").count("？") + (entry.get("stem") or "").count("?") > 1:
            flags.append({"level": "warn", "text": "题干里有多个问号"})
        if len(entry.get("options") or []) != 4:
            flags.append({"level": "warn", "text": f"选项数 {len(entry.get('options') or [])}（默认 4）"})
    elif kind == "cloze":
        mask = _masked(entry.get("text") or "")
        if len(mask) <= 2:
            flags.append({"level": "warn", "text": f"挖空过短：{mask!r}"})
        if re.fullmatch(r"[\d\s]+", mask or ""):
            flags.append({"level": "warn", "text": f"只挖了数字：{mask}"})
        elif len(mask) <= 1:
            flags.append({"level": "warn", "text": f"挖空过短：{mask!r}"})
        if len((entry.get("source_excerpt") or "")) < 12:
            flags.append({"level": "warn", "text": "片段过短"})
    elif kind == "contrast":
        sources = entry.get("sources") or []
        if len(sources) < 2:
            flags.append({"level": "bad", "text": "对比题少于两个引用"})
        quotes = [(s.get("quote") or "").strip() for s in sources]
        if any(len(q) < 12 for q in quotes):
            flags.append({"level": "warn", "text": "引用过短"})
        if len(set(quotes)) != len(quotes):
            flags.append({"level": "bad", "text": "引用重复"})
    return flags


def build_payload(plan: dict, spec, title: str | None = None) -> dict:
    sources = _source_map(spec)
    cards = []
    for entry in plan.get("cards") or []:
        key = entry.get("source_key") or ""
        source = sources.get(key)
        item = {
            "key": key,
            "type": entry.get("type"),
            "kind": entry.get("kind") or "",
            "stem": entry.get("stem") or "",
            "text": entry.get("text") or "",
            "extra": entry.get("extra") or "",
            "q": entry.get("q") or "",
            "a": entry.get("a") or "",
            "options": entry.get("options") or [],
            "answer_index": entry.get("answer_index"),
            "explanation": entry.get("explanation") or "",
            "sources": entry.get("sources") or [],
            "ratio": _ratio(entry) if entry.get("type") == "choice" else None,
            "source": source,
            "flags": _flags(entry, source),
        }
        cards.append(item)
    counts = {
        "cloze": sum(1 for c in cards if c["type"] == "cloze"),
        "choice": sum(1 for c in cards if c["type"] == "choice"),
        "contrast": sum(1 for c in cards if c["type"] == "contrast"),
        "flagged": sum(1 for c in cards if c["flags"]),
        "bad": sum(1 for c in cards if any(f["level"] == "bad" for f in c["flags"])),
    }
    skipped: dict[str, int] = {}
    for item in plan.get("skipped") or []:
        reason = item.get("reason") or "unknown"
        skipped[reason] = skipped.get(reason, 0) + 1
    return {
        "version": 1,
        "title": title or "派生题复核",
        "deck": getattr(spec, "name", ""),
        "counts": counts,
        "skipped": skipped,
        "cards": cards,
    }


_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<style>
  :root { color-scheme: light dark; --bg:#fff; --fg:#1f2328; --mut:#656d76; --line:#d0d7de; --card:#f6f8fa; --ok:#1a7f37; --warn:#9a6700; --bad:#cf222e; --accent:#0969da; }
  @media (prefers-color-scheme: dark) { :root { --bg:#0d1117; --fg:#e6edf3; --mut:#8b949e; --line:#30363d; --card:#161b22; --ok:#3fb950; --warn:#d29922; --bad:#f85149; --accent:#4493f8; } }
  * { box-sizing: border-box; }
  body { margin:0; padding:24px; background:var(--bg); color:var(--fg); font:15px/1.65 -apple-system,BlinkMacSystemFont,"Segoe UI","Noto Sans SC",sans-serif; }
  header { position:sticky; top:0; z-index:5; background:var(--bg); border-bottom:1px solid var(--line); padding-bottom:16px; margin-bottom:20px; }
  h1 { font-size:22px; margin:0 0 4px; }
  .mut { color:var(--mut); font-size:13px; }
  .bar { display:flex; gap:10px; flex-wrap:wrap; align-items:center; margin-top:14px; }
  select,input,button { font:inherit; color:inherit; background:var(--card); border:1px solid var(--line); border-radius:8px; padding:6px 10px; }
  button { cursor:pointer; }
  button.primary { border-color:var(--accent); color:var(--accent); }
  .card { border:1px solid var(--line); border-radius:12px; padding:16px 18px; margin:0 0 14px; background:var(--card); }
  .card.flagged { border-left:4px solid var(--warn); }
  .card.bad { border-left:4px solid var(--bad); }
  .head { display:flex; gap:8px; align-items:center; flex-wrap:wrap; margin-bottom:8px; }
  .badge { font-size:12px; padding:1px 8px; border:1px solid var(--line); border-radius:999px; color:var(--mut); }
  .flag { font-size:12px; padding:1px 8px; border-radius:999px; }
  .flag.warn { color:var(--warn); border:1px solid var(--warn); }
  .flag.bad { color:var(--bad); border:1px solid var(--bad); }
  .stem { font-weight:600; margin:6px 0 10px; }
  ol.opts { list-style:none; padding:0; margin:0 0 10px; }
  ol.opts li { padding:5px 10px; border:1px solid var(--line); border-radius:8px; margin:6px 0; display:flex; gap:8px; }
  ol.opts li.correct { border-color:var(--ok); }
  ol.opts li .mark { color:var(--ok); font-weight:700; }
  ol.opts li .len { margin-left:auto; color:var(--mut); font-size:12px; }
  .cloze mark { background:var(--ok); color:#fff; border-radius:4px; padding:1px 4px; }
  .src { margin-top:10px; border-top:1px dashed var(--line); padding-top:8px; font-size:13px; }
  .src summary { cursor:pointer; color:var(--mut); }
  .src pre { white-space:pre-wrap; word-break:break-word; margin:6px 0; font:inherit; color:var(--mut); }
  .marks { display:flex; gap:6px; flex-wrap:wrap; margin-top:10px; }
  .marks button.on { border-color:var(--accent); color:var(--accent); }
  .marks input { flex:1; min-width:180px; }
  .skiplist { font-size:13px; color:var(--mut); margin-top:8px; }
  .empty { text-align:center; color:var(--mut); padding:40px 0; }
  @media print { header { position:static; } .marks, .bar { display:none; } .card { break-inside:avoid; } }
</style>
</head>
<body>
<header>
  <h1 id="title"></h1>
  <div class="mut" id="sub"></div>
  <div class="bar">
    <select id="type"><option value="">全部类型</option><option value="choice">选择题</option><option value="cloze">填空题</option><option value="contrast">对比题</option></select>
    <label class="mut"><input type="checkbox" id="onlyFlagged"> 只看可疑</label>
    <input id="search" placeholder="搜索题干/答案/源卡" style="min-width:240px">
    <button id="export">导出标记</button>
    <button id="clear">清除标记</button>
    <span class="mut" id="progress"></span>
  </div>
  <div class="skiplist" id="skipped"></div>
</header>
<main id="list"></main>
<script id="payload" type="application/json">__DATA__</script>
<script>
const DATA = JSON.parse(document.getElementById('payload').textContent);
const STORE = 'anki-derive-review:' + DATA.deck;
const marks = JSON.parse(localStorage.getItem(STORE) || '{}');
const esc = (s) => String(s == null ? '' : s).replace(/[&<>"]/g, (c) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const plain = (s) => String(s || '').replace(/<[^>]+>/g, '').replace(/\\s+/g, ' ').trim();
document.getElementById('title').textContent = DATA.title;
document.getElementById('sub').textContent =
  DATA.deck + ' · 选择 ' + DATA.counts.choice + ' / 填空 ' + DATA.counts.cloze +
  ' / 对比 ' + DATA.counts.contrast + ' · 可疑 ' + DATA.counts.flagged + '（硬伤 ' + DATA.counts.bad + '）';
document.getElementById('skipped').textContent = '未出卡：' + Object.entries(DATA.skipped).map(([k,v]) => k + ' ' + v).join(' / ');
function clozeHtml(text) {
  return esc(text).replace(/\\{\\{c1::(.*?)\\}\\}/g, '<mark>$1</mark>');
}
function cardHtml(c, i) {
  const flagged = c.flags.length > 0;
  const bad = c.flags.some(f => f.level === 'bad');
  const flags = c.flags.map(f => '<span class="flag ' + f.level + '">' + esc(f.text) + '</span>').join('');
  let body = '';
  if (c.type === 'choice') {
    const opts = (c.options || []).map((o, k) =>
      '<li class="' + (k === c.answer_index ? 'correct' : '') + '"><span class="mark">' +
      (k === c.answer_index ? '✔' : '') + '</span><span>' + esc(o.text) + '</span><span class="len">' +
      String((o.text || '').length) + ' 字</span></li>').join('');
    body = '<div class="stem">' + esc(c.stem) + '</div><ol class="opts">' + opts + '</ol>' +
      (c.explanation ? '<div class="mut">' + esc(c.explanation) + '</div>' : '');
  } else if (c.type === 'cloze') {
    body = '<div class="cloze">' + clozeHtml(c.text) + '</div>' +
      (c.extra ? '<div class="mut">' + esc(c.extra) + '</div>' : '');
  } else {
    body = '<div class="stem">' + esc(c.q) + '</div><div>' + esc(c.a) + '</div>' +
      '<ul>' + (c.sources || []).map(s => '<li><span class="mut">' + esc(s.key) + '</span> · ' + esc(s.quote) + '</li>').join('') + '</ul>';
  }
  const src = c.source ? '<details class="src"><summary>源卡：' + esc(c.source.q.slice(0, 60)) + '</summary><pre>' +
      esc(c.source.q) + '\\n\\n' + esc(c.source.a) + '\\n\\n定位：' + esc(c.source.locator) +
      ((c.source.pages && c.source.pages.length) ? ' · 页 ' + c.source.pages.join(',') : '') + '</pre></details>' : '';
  const m = marks[c.key] || {};
  const btn = (val, label) => '<button data-key="' + esc(c.key) + '" data-mark="' + val + '" class="' + (m.mark === val ? 'on' : '') + '">' + label + '</button>';
  const markBar = '<div class="marks">' + btn('ok','通过') + btn('unsure','可疑') + btn('bad','错误') +
      '<input data-note="' + esc(c.key) + '" placeholder="备注（可选）" value="' + esc(m.note || '') + '"></div>';
  return '<article class="card ' + (bad ? 'bad' : flagged ? 'flagged' : '') + '" data-type="' + esc(c.type) + '">' +
    '<div class="head"><span class="badge">' + esc(c.type) + '</span>' +
    (c.kind ? '<span class="badge">' + esc(c.kind) + '</span>' : '') +
    (c.ratio != null ? '<span class="badge">长度比 ' + c.ratio + '</span>' : '') +
    '<span class="mut">#' + (i + 1) + ' · ' + esc(c.key) + '</span>' + flags + '</div>' + body + src + markBar + '</article>';
}
function render() {
  const type = document.getElementById('type').value;
  const only = document.getElementById('onlyFlagged').checked;
  const q = document.getElementById('search').value.trim().toLowerCase();
  const list = DATA.cards.filter(c => (!type || c.type === type) && (!only || c.flags.length) &&
    (!q || JSON.stringify(c).toLowerCase().includes(q)));
  document.getElementById('list').innerHTML = list.length ? list.map(cardHtml).join('') : '<div class="empty">没有匹配的卡片</div>';
  const marked = Object.keys(marks).length;
  document.getElementById('progress').textContent = '已标记 ' + marked + ' / ' + DATA.cards.length;
  bind();
}
function bind() {
  document.querySelectorAll('button[data-mark]').forEach(b => b.onclick = () => {
    const k = b.dataset.key, v = b.dataset.mark;
    marks[k] = Object.assign({}, marks[k], {mark: marks[k] && marks[k].mark === v ? '' : v});
    localStorage.setItem(STORE, JSON.stringify(marks)); render();
  });
  document.querySelectorAll('input[data-note]').forEach(inp => inp.onchange = () => {
    const k = inp.dataset.note;
    marks[k] = Object.assign({}, marks[k], {note: inp.value});
    localStorage.setItem(STORE, JSON.stringify(marks));
  });
}
document.getElementById('type').onchange = render;
document.getElementById('onlyFlagged').onchange = render;
document.getElementById('search').oninput = render;
document.getElementById('export').onclick = () => {
  const blob = new Blob([JSON.stringify({deck: DATA.deck, marks}, null, 2)], {type: 'application/json'});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = DATA.deck + '-review-marks.json';
  a.click();
};
document.getElementById('clear').onclick = () => {
  if (!confirm('清除本页所有标记？')) return;
  Object.keys(marks).forEach(k => delete marks[k]);
  localStorage.removeItem(STORE); render();
};
render();
</script>
</body>
</html>
"""


def render_html(payload: dict) -> str:
    data = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    title = f"{payload['title']} · {payload['deck']}".replace("<", "&lt;").replace(">", "&gt;")
    return _TEMPLATE.replace("__TITLE__", title).replace("__DATA__", data)


def write_review(plan_path, deck_dir, out_path=None) -> tuple[Path, dict]:
    plan = load_derived_plan(plan_path)
    spec = load_spec(deck_dir)
    payload = build_payload(plan, spec)
    out = Path(out_path).expanduser() if out_path else Path(plan_path).with_suffix(".review.html")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_html(payload), encoding="utf-8")
    return out, payload["counts"]
