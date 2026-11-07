"""确定性 ID：同一名称（同牌组/同模型）永远得到同一个 Anki ID。

为什么必须确定：
- deck_id 每次变化 → Anki 会把重建的牌组当成新牌组，产生重复牌组、丢复习记录。
- 旧实现 `abs(hash(name))` 在 Python 3 里每进程加盐，属于必错的写法。

规则：只用 sha1(name)，不含时间、不含随机数、不含内置 hash()。
ID 一旦发布就不能改；要新增牌组请用新名字。
"""

from __future__ import annotations

import hashlib

# 两个互不重叠的号段，避免与历史牌组（1.6e9 / 1.9e9 / 2.0e9 等）冲突
MODEL_BASE = 1_600_000_000
DECK_BASE = 1_700_000_000
SPAN = 100_000_000


def stable_int(seed: str, base: int, span: int = SPAN) -> int:
    digest = hashlib.sha1(seed.encode("utf-8")).hexdigest()
    return base + int(digest[:12], 16) % span


def model_id(deck_name: str, kind: str) -> int:
    """每个牌组各自一套 note type，避免复用别人的模型名。kind: basic|cloze。"""
    return stable_int(f"model::{deck_name}::{kind}", MODEL_BASE)


def deck_id(deck_name: str) -> int:
    return stable_int(f"deck::{deck_name}", DECK_BASE)
