#!/usr/bin/env python3
"""
PDF-to-Anki Card Builder Pipeline

Converts Android interview PDFs, txt, and md files into Anki flashcards (.apkg).

Usage:
    python3 main.py

Requires:
    - ANTHROPIC_API_KEY environment variable (for AI-powered generation)
    - pymupdf4llm, genanki, anthropic, fitz packages

Architecture:
    src/
    ├── config.py          # Pipeline configuration
    ├── models.py          # Flashcard data model
    ├── utils.py           # Text normalization, cleaning, domain detection
    ├── parsers/
    │   ├── interview_pdf.py    # Regex-based Q&A parser for interview PDFs
    │   ├── knowledge_pdf.py    # Heading-based + AI parser for reference PDFs
    │   ├── txt.py              # TXT file question parser with AI answers
    │   └── kotlin_md.py        # Kotlin coroutine markdown Q&A parser
    ├── processing/
    │   ├── deduplicator.py     # Deduplication across sources
    │   └── quality_filter.py   # Quality validation
    ├── export/
    │   └── anki_exporter.py    # genanki .apkg export
    └── pipeline.py             # Pipeline orchestrator
"""

import logging
import sys

from src.pipeline import main

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)

if __name__ == "__main__":
    sys.exit(main())
