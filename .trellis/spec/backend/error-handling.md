# Error Handling

> How errors are handled in this project.

---

## Overview

This is a CLI pipeline, not a long-running service. Error handling focuses on graceful degradation and informative failure messages.

---

## Error Handling Patterns

### PDF Extraction Failures

```python
try:
    doc = fitz.open(pdf_path)
except Exception as e:
    logger.error(f"无法打开 PDF: {pdf_path}, 错误: {e}")
    return []  # Return empty result, continue with other files
```

**Principle**: One broken file should not crash the entire pipeline.

### API Call Failures

When `ANTHROPIC_API_KEY` is not set or API calls fail:
```python
if not os.getenv("ANTHROPIC_API_KEY"):
    print("⚠️ ANTHROPIC_API_KEY 未设置，使用 fallback 模式")
    return self._extract_basic_cards(sections)  # Fallback path
```

**Principle**: AI generation is optional enhancement, not critical path.

### Card Validation

```python
# Per-card validation with partial success
valid_cards = []
for card in cards:
    if quality_filter.is_valid(card):
        valid_cards.append(card)
    else:
        logger.warning(f"跳过无效卡片: {card.front[:50]}...")

return valid_cards  # Accept partial results
```

**Principle**: Accept partial success — skip individual failures rather than failing the entire batch.

---

## Common Mistakes

### Mistake: Not handling genanki HTML warnings

**Symptom**: genanki warns about unescaped angle brackets in field content

**Cause**: PDF content contains `<`, `>`, `<=`, `->`, and Java generics like `<K,V>`

**Fix**: Escape angle brackets before passing to genanki:
```python
def escape_html(text: str) -> str:
    text = re.sub(r'<(?=[^/\w])', '&lt;', text)  # Standalone <
    text = re.sub(r'(?<=\w)>', '&gt;', text)      # Standalone >
    return text
```

### Mistake: Overly aggressive quality filters

**Symptom**: Valid cards from txt files being dropped by quality filter

**Cause**: Applying the same strict thresholds to all source types. TXT question cards have shorter fronts than PDF-extracted cards.

**Fix**: Use per-source or type-aware quality thresholds. Don't require `？` in the front for all card types.
