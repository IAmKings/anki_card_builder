# Research: PDF to Anki Flashcard Conversion Approaches

- **Query**: Best approaches for converting Chinese technical/educational PDF content into Anki flashcards
- **Scope**: External (web search) + Internal (.trellis/spec review)
- **Date**: 2026-06-08

## Findings

### 1. PDF Text Extraction Libraries

#### Primary Recommendation: PyMuPDF + pymupdf4llm

| Library | Strengths | Weaknesses | Best For |
|---------|-----------|------------|----------|
| **PyMuPDF (fitz)** | Fastest C engine, layout-aware, multi-column, table detection, font-size-based heading detection | Slightly larger memory footprint | General-purpose extraction, the clear winner |
| **pymupdf4llm** | One-call Markdown output, heading detection via font size (`#` syntax), table-to-Markdown, LLM/RAG-optimized | Depends on PyMuPDF (not standalone) | Direct LLM ingestion |
| **pdfplumber** | Excellent table extraction, character-level positioning, visual debugging | Slower, no heading detection, no OCR | Complex table extraction, precise layout needs |
| **PyPDF2 / pypdf** | Lightweight, simple API | No layout, no tables, no OCR | Quick text-only extraction (not recommended for this task) |
| **MinerU** | Deep layout analysis (text/title/image/table/formula detection), trained on Chinese docs | Heavy, needs GPU, complex setup | High-fidelity Chinese document extraction (overkill for text-based PDFs) |

**Recommendation for these PDFs**: Both PDFs are PDF 1.7 (text-based, not scanned). Use **PyMuPDF4LLM** as the primary extractor. It handles:
- Chinese text natively (Unicode-aware)
- Multi-column layouts
- Heading detection by font size
- Table extraction as Markdown
- Optional OCR fallback if any pages are scanned

```python
import pymupdf4llm

# Get full document as markdown text
md_text = pymupdf4llm.to_markdown("input.pdf")

# Or get per-page chunks with metadata
page_chunks = pymupdf4llm.to_markdown("input.pdf", page_chunks=True)
# Each chunk: {"text": "...", "metadata": {"page": 1, ...}}
```

#### Chinese-Specific PDF Tools

- **PDF-Extract-Kit** (seacent/PDF-Extract-Kit): Uses LayoutLMv3 for layout detection + YOLOv8 for formula detection + PaddleOCR for Chinese OCR. Trained on diverse Chinese docs (textbooks, research reports, financial documents). But requires GPU and is heavy.
- **pdf_sword** (reskfa/pdf_sword): Intelligent chapter splitting for Chinese PDFs. Built-in patterns for Chinese chapter/section numbering ("第一章", "1.1", "一、"等). Can use LLM to auto-detect structure.

Since both PDFs are text-based (PDF 1.7), heavy OCR pipelines like PDF-Extract-Kit are unnecessary. pymupdf4llm is sufficient.

---

### 2. Chunking Strategies for Knowledge-Reference PDF

The reference book (352 pages of Android knowledge notes) needs to be split into digestible chunks for LLM processing.

#### Strategy A: Heading-Based Section Splitting (Recommended)

This is the approach used by shimo4228/pdf2anki and epub2anki and is considered best practice.

**Pipeline:**
1. Extract to Markdown via `pymupdf4llm` (which already adds `#` heading markers)
2. Split at `##` or `###` heading boundaries (each section is a semantic unit)
3. Attach a "breadcrumb" context (chapter > section > subsection) to each chunk
4. If a section is very short (under ~500 chars), merge it with the next section
5. If a section is very long (over ~15000 chars), sub-split at the next sub-heading

```python
# Pseudocode for section splitting
sections = split_by_headings(markdown_text, level=2)  # Split at ##
for section in sections:
    breadcrumb = extract_breadcrumb(section)  # "Home > Chapter 3 > Activity Lifecycle"
    chunk = f"[Context: {breadcrumb}]\n\n{section.content}"
    chunks.append(chunk)
```

**Key insight** (from shimo4228's blog post): When feeding long text to an LLM, split at **semantic boundaries** not character counts. Mechanical character-count splitting destroys context. Attaching "where are we in the document" metadata to each chunk significantly improves output quality.

#### Strategy B: Page-by-Page Processing (Fallback)

Used by elpadev/doc-to-anki-with-llm. Each page is processed independently, with adjacent pages (prev/next) sent as context. This increases token usage ~3x but is simpler to implement.

#### Strategy C: MarkdownTextSplitter (LangChain)

```python
from langchain.text_splitter import MarkdownTextSplitter

splitter = MarkdownTextSplitter(chunk_size=5000, chunk_overlap=200)
docs = splitter.create_documents([md_text])
```

This is the simplest approach but has no breadcrumb context. Works for initial prototyping.

**Recommended: Strategy A (Heading-Based) for the reference book, Strategy C (per-page) for the interview PDF.**

---

### 3. Parsing the Interview Q&A PDF (Already Q&A Format)

The second PDF (354 pages, interview questions with answers) already has a Q&A structure. The approach here is different:

#### Approach: Regex-Based Pattern Matching + Structure Detection

1. Extract to Markdown via pymupdf4llm
2. Analyze the document structure to detect Q&A patterns. Common patterns in Chinese interview books:
   - Numbered: "1. xxx？" followed by answer paragraphs
   - "Q: ... A: ..." format
   - Heading-based: "## 问题标题" followed by answer content
3. Use regex to split into Q&A pairs

```python
import re

# Possible patterns for Chinese interview Q&A
patterns = [
    r"(\d+[.、]\s*.*?[？?])\s*\n(.+?)(?=\n\d+[.、]|\Z)",  # "1. xxxx？" pattern
    r"(?:问[：:])\s*(.+?)\s*\n(?:答[：:])\s*(.+?)(?=\n(?:问[：:]|\Z))",  # "问：... 答：..." pattern
    r"(?:Q[：:])\s*(.+?)\s*\n(?:A[：:])\s*(.+?)(?=\n(?:Q[：:]|\Z))",  # "Q: ... A: ..." pattern
]
```

4. If regex fails, use LLM to identify the structure from the first N pages, then generate custom patterns
5. Validate each Q&A pair (both question and answer must have content)

**Key advantage**: This PDF already has Q&A pairs, so LLM-based Q&A generation is NOT needed for this file. Direct parsing and formatting into Anki cards is sufficient.

---

### 4. LLM-Based Q&A Generation (For the Reference Book PDF)

#### Should We Use an LLM?

**Verdict: YES, but with important caveats.**

The reference book (352 pages of Android knowledge) is textbook-style. There are no explicit Q&A pairs. An LLM is the best tool to extract the key concepts and generate well-formed Q&A pairs.

#### Existing Systems Using LLMs

| Project | LLM Used | Approach | Cost |
|---------|----------|----------|------|
| **cwilharm/pdf-to-anki-cards** | GPT-4o-mini | Streamlit app, 3 card types | ~$0.06/100 pages |
| **shimo4228/pdf2anki** | Claude API | Wozniak-based prompts, QA pipeline | Tracks cost via API |
| **hegstadjosh/pdf-to-anki** | Multi-model (OpenAI, Claude, Perplexity) | GUI, customizable prompts | N/A |
| **AykoSc/pdfs-to-anki-cards** | OpenAI GPT | Config-driven (YAML) | N/A |
| **epub2anki** | Claude (claude-haiku-4-5) | Batch API for 50% savings, SQLite cache | N/A |

#### Pros of LLM-Based Generation

1. **Concept understanding**: LLM can extract truly important concepts vs. trivial details
2. **Format transformation**: Can convert prose paragraphs into atomic Q&A pairs
3. **Natural language**: Generates well-phrased questions
4. **Multiple card types**: Can produce Basic, Cloze, Reversible, and Compare/Contrast cards
5. **Bloom's taxonomy**: Can generate cards at different cognitive levels (remember, understand, apply)

#### Cons and Risks

1. **Hallucination**: LLM may generate incorrect information not in the source
2. **Missing context**: May create cards about concepts not fully explained in the visible text
3. **Quality inconsistency**: Single-pass generation may produce variable quality
4. **Cost**: Each page costs ~$0.0006 with GPT-4o-mini; 352 pages = ~$0.20/total (actually cheap)
5. **Prompt sensitivity**: Output quality heavily depends on prompt design

#### Best Practice: Prompt Design

Based on **Wozniak's 20 Rules of Formulating Knowledge** and analysis of successful systems:

```python
SYSTEM_PROMPT = """You are an expert flashcard creator following Wozniak's principles:
1. Atomicity: One concept per card, answerable in under 6 seconds
2. Clarity: Each question must have exactly one correct answer
3. Simplicity: Use simple, direct language
4. Avoid enumerations: Split lists into individual items
5. Use mnemonics: Include memory techniques where appropriate

Generate Anki flashcards from the provided text in JSON format:
{"cards": [
    {"front": "question", "back": "answer", "tags": ["tag1", "tag2"]},
    ...
]}

Target approximately 3-8 cards per section chunk.
"""
```

Key prompt elements from successful systems:
- **Breadcrumb context**: Tell the LLM where in the document the chunk belongs
- **Output format enforcement**: Use structured JSON, validate each card
- **One concept per card**: The single most important rule
- **Avoid "yes/no" questions**: They are poor for spaced repetition

---

### 5. Existing Open-Source Tools for PDF to Anki

#### Most Relevant (to steal architecture from):

| Tool | Stars | Key Innovation | Relevance |
|------|-------|----------------|-----------|
| **shimo4228/pdf2anki** | ~1 | Best quality pipeline. Uses pymupdf4llm + heading splitting + 6-dim quality scoring + Wozniak prompts + deduplication | **HIGH** - Best reference architecture |
| **cwilharm/pdf-to-anki-cards** | New | Streamlit UI, OCR fallback, 3 card types, quality filter, ~$0.06/100pgs | MEDIUM - Nice UI approach |
| **hegstadjosh/pdf-to-anki** | ~1 | Multi-model support (OpenAI/Claude/Perplexity), customtkinter GUI | MEDIUM - Multi-LLM support |
| **AykoSc/pdfs-to-anki-cards** | ~1 | Config-driven (YAML), split by PDF | LOW - Simple approach |
| **elpadev/doc-to-anki-with-llm** | New | Page-by-page + adjacent context, CLI | LOW - Simple but no quality checks |
| **epub2anki** | New | TOC-based splitting, Claude Batch API for 50% savings, SQLite cache | MEDIUM - Batch API + caching ideas |
| **anki-llm (raine)** | New | TUI, duplicate detection, quality processing pipeline | MEDIUM - Duplicate detection approach |

#### Libraries to Use Directly:

| Library | Purpose | Stars | Notes |
|---------|---------|-------|-------|
| **genanki** | Generate .apkg files | 3K+ stars | **This is the go-to**. Handles Models, Notes, Decks, Packages, media files |
| **pymupdf4llm** | PDF to Markdown | Part of PyMuPDF ecosystem | Best for LLM ingestion |
| **PyMuPDF (fitz)** | Raw PDF manipulation | Very popular | Underlying engine for pymupdf4llm |
| **jieba** | Chinese text segmentation | Very popular | Only needed if doing explicit Chinese NLP analysis |
| **pdfplumber** | Table extraction | Popular | Optional, as fallback for layout issues |

---

### 6. Chinese Text Processing Considerations

#### PDF Extraction (Chinese Specific)

- **pymupdf4llm handles Chinese text natively** - No special handling needed. It outputs Unicode/Markdown.
- Both PDFs are PDF 1.7 (not scanned), so OCR is not needed.
- Chinese character encoding is Unicode; pymupdf4llm outputs UTF-8 by default.
- Chinese punctuation (。？！、：；""''（）【】) is preserved as-is.

#### Segmentation (jieba)

For this specific task, **jieba segmentation is not needed** for the core pipeline. The LLM handles the content understanding.

When jieba IS useful:
- Building a keyword index for deduplication
- Generating tag suggestions from card content
- Analyzing document structure (TF-IDF key phrase extraction)

```python
import jieba
import jieba.analyse

# Extract key phrases from content for tagging
keywords = jieba.analyse.extract_tags(content, topK=5, withWeight=True)
# Returns [("Activity", 0.85), ("生命周期", 0.72), ("onCreate", 0.68)]
```

For Android-specific content, adding custom dictionary entries improves accuracy:
```python
jieba.add_word("Activity")
jieba.add_word("Fragment")
jieba.add_word("Intent")
jieba.add_word("BroadcastReceiver")
jieba.add_word("ContentProvider")
jieba.add_word("AndroidManifest")
```

#### Text Cleaning

Chinese technical text cleanup steps:
1. Remove page headers/footers (page numbers, "Android核心知识点笔记" repeated headers)
2. Normalize whitespace (Chinese text uses no spaces between words, but spaces around code/variables)
3. Fix line-break issues (PDF extraction may insert newlines mid-sentence)
4. Preserve code blocks (indentation-sensitive; don't reformat)
5. Handle mixed Chinese+English content (Android docs have lots of English keywords)

---

### 7. Card Quality Assurance

#### Dimensions of Quality (from pdf2anki's 6-dim system)

| Dimension | Description | Scoring |
|-----------|-------------|---------|
| **Front quality** | Is the question/prefix clear and well-phrased? | 0-1 |
| **Back quality** | Is the answer accurate and complete? | 0-1 |
| **Card type fit** | Is the card type (Basic/Cloze) appropriate? | 0-1 |
| **Bloom level fit** | Is the cognitive level appropriate for the content? | 0-1 |
| **Tags quality** | Are tags meaningful and consistent? | 0-1 |
| **Atomicity** | Does the card test exactly one concept? | 0-1 |

**Quality threshold**: Cards scoring below 0.90 weighted sum should be flagged for review.

#### Deduplication Strategies

1. **Exact text match**: Simple, catches obvious duplicates
2. **Fuzzy match via embeddings**: Use sentence embeddings + cosine similarity (threshold ~0.85)
3. **LLM critique**: Send pairs of suspect-duplicate cards to LLM for judgment
4. **Cross-section dedup** (from pdf2anki): After extracting cards per section, scan all sections for near-duplicate cards

```python
# Simple dedupe by front text normalization
from difflib import SequenceMatcher

def is_duplicate(front1, front2, threshold=0.85):
    # Normalize: remove punctuation, lowercase, strip whitespace
    norm = lambda s: re.sub(r'[^\w]', '', s).lower()
    return SequenceMatcher(None, norm(front1), norm(front2)).ratio() > threshold
```

#### Validation Pipeline (3-Layer)

Based on "Never Trust LLM Output" blog post by shimo4228:

1. **Structural validation**: Is the JSON parseable? Does each card have front/back/tags?
2. **Heuristic quality scoring**: Rule-based checks (length minimums, no empty fields, no placeholder text)
3. **LLM critique**: For cards below threshold, send to LLM for improvement suggestions

**Defense in depth**: Validate per card and accept partial success. Instead of retrying the whole batch, skip individual failures and log them for resilience.

---

### 8. Recommended Architecture

```
PDF Input
    |
    v
[Step 1] PyMuPDF4LLM Extraction
    |-- Knowledge Ref Book: to_markdown() with page_chunks=True
    |-- Interview PDF: to_markdown() with page_chunks=True
    |
    v
[Step 2] Structure Analysis
    |-- Knowledge Ref Book: Heading-based section splitting (##, ###)
    |   + breadcrumb context ("Chapter 3 > Activity Lifecycle")
    |-- Interview PDF: Q&A pattern detection (regex + optional LLM)
    |   + direct parse into Q&A pairs
    |
    v
[Step 3a] For Reference Book: LLM Q&A Generation
    |-- Per section chunk: Claude API / OpenAI API
    |-- Wozniak-based prompt + breadcrumb context
    |-- Output: structured JSON {front, back, tags}
    |
[Step 3b] For Interview PDF: Direct card creation
    |-- Parsed Q&A pairs → directly format as cards
    |-- No LLM needed (unless text cleaning is required)
    |
    v
[Step 4] Quality Assurance
    |-- Validate each card (front/back present, reasonable length)
    |-- Deduplicate (cross-section, similarity check)
    |-- Optional: LLM critique for low-confidence cards
    |
    v
[Step 5] genanki Export
    |-- Define Model (Question + Answer fields, Basic card type)
    |-- Create Notes from each Q&A pair
    |-- Add tags for organization
    |-- Package → output.apkg
    |
    v
[Step 6] Manual Review
    |-- Import into Anki
    |-- Human review of at least 10 cards
    |-- Adjust prompts/pipeline as needed
```

#### Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| PDF Extractor | pymupdf4llm | Best for text-based PDFs, handles Chinese, heading detection, no GPU needed |
| .apkg Generator | genanki | Mature, 3K+ stars, handles all Anki formats |
| LLM for Q&A Gen | Claude API or OpenAI GPT-4o-mini | Both work well; GPT-4o-mini cheaper ($0.06/100pgs) |
| Chunking | Heading-based section split | Preserves semantic context, proven in pdf2anki |
| Interview PDF | Direct regex parse, no LLM | Already Q&A format, LLM would add cost and risk |
| Quality Filter | Heuristic + similarity dedup | Simple, no extra LLM cost for basic filtering |
| Tags | By chapter/section + technology area | Enables filtered study in Anki |

#### Cost Estimate (Reference Book Only)

With GPT-4o-mini:
- ~350 pages, split into ~50-80 sections
- ~50-80 LLM calls
- ~100K-150K input tokens, ~20K-30K output tokens
- Estimated cost: **$0.15 - $0.30**

With Claude Haiku:
- Similar token counts
- Estimated cost: **$0.20 - $0.40**

Total for both PDFs: under **$1.00**

---

### 9. Related Specs

- `/.trellis/tasks/06-08-pdf-to-anki/prd.md` — Original PRD for this task, specifying 2 PDFs, target of 100+ cards, .apkg output format.

### 10. Key Caveats

1. **LLM hallucinations are the #1 risk**: Always include "verify with source" instruction in prompt, and consider human review of generated cards.
2. **PDF extraction quality varies**: Even with pymupdf4llm, complex page layouts (code blocks spanning columns, nested tables) may produce garbled text. Plan for manual spot-checking of extracted text.
3. **The interview PDF may have answer formatting**: Answers may include code blocks, bullet points, or images. genanki supports HTML formatting in card fields, so preserve Markdown formatting.
4. **Duplicate content between PDFs**: Both Android knowledge and interview books will have significant overlap on core topics (e.g., Activity lifecycle, Handler mechanism). Cross-deck deduplication is important.
5. **Tags are important for utility**: Without tags (by chapter/topic), 100+ cards in a single deck are hard to study selectively. Anki supports nested decks and tags.
6. **No existing project code to reuse**: This is a greenfield project. The research above identifies libraries and reference architectures but no existing code in this repo.
