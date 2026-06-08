# Quality Guidelines

> Code quality standards for this project.

---

## Overview

Code quality is enforced via:
- **mypy** — static type checking (0 errors required)
- **pylint** — code style and quality (10.00/10 target)
- **syntax check** — `python3 -m py_compile`

---

## Forbidden Patterns

### Don't: Raw PDF text splitting without structure

```python
# BAD: mechanical character-count splitting loses context
chunks = [text[i:i+5000] for i in range(0, len(text), 5000)]
```

**Why**: Destroys semantic boundaries. PDF content must be split at heading/paragraph boundaries.

**Instead**:
```python
# GOOD: heading-based semantic splitting
sections = split_by_headings(markdown_text, level=2)
```

### Don't: Generate cards from TOC/directory pages

**Why**: Table of contents pages produce garbage cards like "简述：目录..."

**Detection**: Use `is_toc_content()` function to filter:
- Short numbered entries with page references
- Section titles like "目录", "前言", "附录"

### Don't: Placeholder-style questions

```python
# BAD: vague fill-in-the-blank pattern
"关于 {title}，以下说法正确的是？"
```

**Why**: Not useful for spaced repetition. Questions must be specific and testable.

---

## Required Patterns

### Do: Use dataclasses for configuration

```python
from dataclasses import dataclass, field

@dataclass
class Config:
    data_dir: str = "data"
    output_dir: str = "output"
    similarity_threshold: float = 0.85
    model_id: int = 1607392319
```

### Do: Source annotation on every card

Every card must include:
- `source` field: source filename + chapter/section path
- `tags`: at minimum `source_<filename>` and `topic_<domain>`

### Do: Graceful degradation without API key

The pipeline must work (with reduced quality) when `ANTHROPIC_API_KEY` is not set:
- Knowledge PDF: fall back to heading-based content extraction
- TXT files: mark answers as "【待补充答案】"

### Do: Quality filter pipeline

```python
# 3-layer validation
1. Structural: non-empty front/back, valid JSON
2. Heuristic: minimum char counts, no placeholder text
3. Content: detect gibberish, TOC artifacts, broken fragments
```

---

## Card Quality Standards

| Check | Threshold | Action |
|-------|-----------|--------|
| Front min length | 5+ Chinese chars | Drop card |
| Back min length | 10+ Chinese chars | Drop card |
| Front has question mark | `？` or `?` present | Prefer, not required |
| No TOC artifacts | `is_toc_content()` | Drop card |
| No placeholder patterns | "以下说法正确的是" | Drop card |
| No broken prefixes | "什么是3 方法？" | Strip numeric prefix |

---

## Testing Requirements

Currently: manual spot-check of 10+ cards from output report.

Future: automated validation of:
- Card count per source meets minimums
- .apkg file validity (zip + SQLite structure)
- Deduplication accuracy
