"""TXT 物理行解析：与 ingest 的 line:N 定位保持同一套计数。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TxtLine:
    line: int
    text: str
    chars: int


def iter_txt_lines(text: str):
    """按 splitlines() 逐行产出；空行也计数，行号从 1 开始。"""
    for number, line in enumerate(text.splitlines(), 1):
        yield TxtLine(line=number, text=line, chars=len(line.strip()))
