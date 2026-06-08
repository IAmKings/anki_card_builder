# Directory Structure

> How backend code is organized in this project.

---

## Overview

This is a Python CLI pipeline project. Code is organized as modular scripts with clear input/output separation.

---

## Directory Layout

```
anki_card_builder/
├── main.py              # Main pipeline entry point
├── data/                # Input files (PDF, txt) — read-only
├── output/              # Generated .apkg and reports
├── .trellis/            # Project management (specs, tasks, workflow)
└── requirements.txt     # Python dependencies (if created)
```

---

## Module Organization

Currently a single-file pipeline (`main.py`) organized into logical sections:

1. **Configuration** — `Config` dataclass with paths, model IDs, thresholds
2. **Data Models** — `Flashcard` dataclass
3. **Utility Functions** — text normalization, similarity, domain detection
4. **Parsers** — one class per source type (`InterviewPDFParser`, `KnowledgePDFParser`, `TxtParser`)
5. **Processing** — `Deduplicator`, `QualityFilter`
6. **Export** — `AnkiExporter` (genanki wrapper)
7. **Pipeline** — `main()` orchestrator

When the file exceeds ~2000 lines, split into `src/` package:
```
src/
├── config.py
├── models.py
├── parsers/
│   ├── interview_pdf.py
│   ├── knowledge_pdf.py
│   └── txt.py
├── processing/
│   ├── deduplicator.py
│   └── quality_filter.py
├── export/
│   └── anki_exporter.py
└── pipeline.py
```

---

## Naming Conventions

| Type | Convention | Example |
|------|-----------|---------|
| Files | `snake_case.py` | `quality_filter.py` |
| Classes | `PascalCase` | `InterviewPDFParser` |
| Functions | `snake_case` | `extract_markdown()` |
| Constants | `UPPER_SNAKE_CASE` | `MODEL_ID` |
| Private methods | `_method_name` | `_extract_qa_pairs()` |

---

## Dependencies

Core dependencies:
- `pymupdf4llm` — PDF to Markdown extraction
- `genanki` — .apkg file generation
- `anthropic` — Claude API for AI-powered Q&A generation (optional, fallback available)

Install: `pip3 install pymupdf4llm genanki anthropic`
