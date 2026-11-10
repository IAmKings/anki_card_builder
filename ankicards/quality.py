"""内容层质量规则（Q1–Q9）：确定性、无 IO、不依赖 ingest。

定位：只回答「按文本看这张卡是否可疑」，**不回答**「这个知识点值不值得背」。
后者没有外部可验证标准，属于人的判断；这里只把可疑项显式列出来，交给
`import` 的报告和人的抽样复核。

默认全部**不阻断**：error 级也只在 `import --strict` 下让命令失败，
以免改变已发布牌组的产出。规则本身必须保持可判定、可回归，不引入随机性。
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass

ERROR = "error"
WARNING = "warning"

#: 规则号 → 一句话含义；报告、文档、测试共用这张表。
RULE_TEXT = {
    "Q1": "答案过短",
    "Q2": "答案疑似被截断",
    "Q3": "答案只有交叉引用",
    "Q4": "正面是版面词而非概念",
    "Q5": "正面与答案近乎重复",
    "Q6": "答案过长",
    "Q7": "表头被当成数据",
    "Q8": "一卡塞多个知识点",
    "Q9": "答案结尾不完整",
}

#: 规则号 → 级别。error 表示「大概率不可背」，warning 表示「值得看一眼」。
RULE_LEVEL = {
    "Q1": ERROR,
    "Q2": ERROR,
    "Q3": ERROR,
    "Q4": WARNING,
    "Q5": ERROR,
    "Q6": WARNING,
    "Q7": WARNING,
    "Q8": WARNING,
    "Q9": WARNING,
}

MIN_ANSWER_CHARS = 6
MAX_ANSWER_CHARS = 200
SIMILARITY_LIMIT = 0.8

#: 答案以这些符号收尾，说明它大概率只是半句（下一行/下一个子项被切掉了）。
DANGLING_END = "；;，,、：:"
#: 一个完整答案应有的收尾字符。
SENTENCE_END = "。！？!?…；;.）)】」』”\"'"
#: 答案之后还剩这么多字，且答案本身没有收尾标点，才判为「被截断」。
TRUNCATED_TAIL_CHARS = 6

_CROSS_REF = re.compile(
    r"(?:见|参见|详见|参考)\s*"
    r"(?:第\s*[0-9一二三四五六七八九十百]+\s*[节章条]|上文|下文|上表|下表|前文|后文|附录)")
_BARE_REF = {"略", "同上", "待补充", "见上文", "见下文", "如前"}
_STEP_WORDS = ("第一步", "第二步", "步骤", "注意", "说明", "示例", "小结", "总结", "提示")
_NUMBERED = re.compile(r"(?:^|[\s；;。])[0-9]+[.、)．]")
_TAG = re.compile(r"<[^>]+>")

#: 表格判定词表。定义在这里而不是 adapters，避免 quality ↔ adapters 循环导入；
#: adapters 从这里取同一份真值。
TABLE_HEADERS = {"解释", "说明", "定义", "含义", "描述", "内容"}
TABLE_FIRST_CELLS = {"概念", "术语", "名称", "字段", "项目", "关键词",
                     "题目", "问题", "主题", "类别", "参数", "属性", "指标", "符号"}


@dataclass(frozen=True)
class Finding:
    rule: str
    level: str
    message: str


def _plain(value) -> str:
    """去掉 HTML 标签与不可见空白，避免把排版算进字数。"""
    if not isinstance(value, str):
        return ""
    return _TAG.sub(" ", value).replace("\u00a0", " ").strip()


def _norm(text: str) -> str:
    return re.sub(r"\s+", "", text)


def _make(rule: str, message: str) -> Finding:
    return Finding(rule=rule, level=RULE_LEVEL[rule], message=message)


def _fields(card: dict) -> tuple[str, str]:
    """返回 (正面, 答案)。cloze 用 text/extra，其余用 q/a。"""
    if card.get("type") == "cloze":
        return str(card.get("text") or ""), str(card.get("extra") or "")
    return str(card.get("q") or ""), str(card.get("a") or "")


def check_card(card: dict, unit_text: str | None = None) -> list[Finding]:
    """对一张卡做全部规则检查，返回 findings（可能为空）。

    unit_text 是这张卡对应的源单元原文（ingest 里那一段）。给了就能发现
    「答案只是原文的前半句」；不给时只按答案本身的收尾符号判断。
    """
    prompt, answer = _fields(card)
    prompt_plain, answer_plain = _plain(prompt), _plain(answer)
    findings: list[Finding] = []

    if len(answer_plain) < MIN_ANSWER_CHARS:
        findings.append(_make("Q1", f"答案只有 {len(answer_plain)} 个字符，无法独立作答"))

    truncated = answer_plain.endswith(tuple(DANGLING_END))
    if not truncated and unit_text:
        unit, body = _norm(_plain(unit_text)), _norm(answer_plain)
        pos = unit.find(body) if body else -1
        tail = len(unit) - (pos + len(body)) if pos >= 0 else 0
        truncated = (pos >= 0 and tail >= TRUNCATED_TAIL_CHARS
                     and not answer_plain.endswith(tuple(SENTENCE_END)))
    if truncated:
        findings.append(_make("Q2", f"答案结尾是「{answer_plain[-1] if answer_plain else ''}」，疑似被截断"))

    if answer_plain in _BARE_REF or _CROSS_REF.search(answer_plain):
        findings.append(_make("Q3", "答案只有指向别处的引用，没有可背的内容"))

    if any(word in prompt_plain for word in _STEP_WORDS):
        findings.append(_make("Q4", "正面是步骤/版面词，不像一个概念"))

    if prompt_plain and answer_plain:
        ratio = difflib.SequenceMatcher(None, _norm(prompt_plain), _norm(answer_plain)).ratio()
        if ratio >= SIMILARITY_LIMIT:
            findings.append(_make("Q5", f"正面与答案相似度 {ratio:.2f}，等于没给答案"))

    if len(answer_plain) > MAX_ANSWER_CHARS:
        findings.append(_make("Q6", f"答案 {len(answer_plain)} 字，超过 {MAX_ANSWER_CHARS} 字，建议拆卡"))

    cells = [prompt_plain] + [part.strip() for part in answer_plain.split("|")]
    header_row = len(cells) >= 2 and (
        all(c in TABLE_HEADERS for c in cells)
        or (cells[0] in TABLE_FIRST_CELLS
            and all(c in TABLE_HEADERS for c in cells[1:])))
    if header_row:
        findings.append(_make("Q7", "整行都是表头词，表头被当成了一行数据"))

    if len(_NUMBERED.findall(answer_plain)) >= 2:
        findings.append(_make("Q8", "答案里有多个并列编号点，一卡塞了多个知识点"))

    if len(answer_plain) > 20 and answer_plain[-1] not in SENTENCE_END:
        findings.append(_make("Q9", f"答案以「{answer_plain[-1]}」结尾，可能不是完整句子"))

    return findings
