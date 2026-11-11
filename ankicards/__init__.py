"""Anki deck toolkit: schema, deterministic ids, build, verify.

设计原则：
- 代码只负责「错了会静默产出坏包」的不变量（ID、契约、媒体、转义、退出码）。
- 判断类工作（读新格式、裁图取值、事实校对）留给 skill 与使用者。
"""

from .schema import CARD_TYPES, DeckSpec, Report, load_spec, validate
from .ids import deck_id, model_id, stable_int

__all__ = [
    "CARD_TYPES",
    "DeckSpec",
    "Report",
    "load_spec",
    "validate",
    "deck_id",
    "model_id",
    "stable_int",
]
__version__ = "0.4.3"
