# Research: Anki .apkg Format and genanki Library

- **Query**: How to use genanki to create Anki .apkg files, supported card models, deck organization, tags, limitations, .apkg internal format, and alternative libraries.
- **Scope**: External (web search for genanki docs, Anki format specs, community resources)
- **Date**: 2026-06-08

## Findings

### 1. genanki Library Overview

**genanki** (v0.13.1, by Kerrick Staley) is the de facto standard Python 3 library for programmatically generating Anki `.apkg` deck files. It is available on PyPI (`pip install genanki`) and is actively maintained with ~3K stars on GitHub.

**Core concepts** (4-tier hierarchy):
- **Model** -- defines the card template (fields and card layouts)
- **Note** -- a single fact/entry that contains field values
- **Deck** -- a collection of notes
- **Package** -- the final `.apkg` file that wraps one or more decks

**Basic workflow:**
```python
import genanki

# 1. Define a model (card template)
model = genanki.Model(
    1607392319,            # unique model ID, generate once with random.randrange(1<<30, 1<<31)
    'Simple Model',
    fields=[
        {'name': 'Question'},
        {'name': 'Answer'},
    ],
    templates=[
        {
            'name': 'Card 1',
            'qfmt': '{{Question}}',
            'afmt': '{{FrontSide}}<hr id="answer">{{Answer}}',
        },
    ])

# 2. Create notes
note = genanki.Note(
    model=model,
    fields=['Capital of Argentina', 'Buenos Aires'])

# 3. Add notes to a deck
deck = genanki.Deck(
    2059400110,            # unique deck ID, generate once and hardcode
    'Country Capitals')
deck.add_note(note)

# 4. Package and write .apkg file
genanki.Package(deck).write_to_file('output.apkg')
```

---

### 2. Supported Card Models

genanki supports two model types via `model_type` parameter on `genanki.Model`:

#### 2a. Front/Back (Basic) -- `model_type=0` (default)

This is the standard question-answer card type. One Note produces one Card.

```python
model = genanki.Model(
    1607392319,
    'Basic Model',
    fields=[
        {'name': 'Question'},
        {'name': 'Answer'},
    ],
    templates=[{
        'name': 'Card 1',
        'qfmt': '{{Question}}',
        'afmt': '{{FrontSide}}<hr id="answer">{{Answer}}',
    }])
```

To create a **reversed card** (both Q->A and A->Q), add a second template:

```python
templates=[
    {
        'name': 'Card 1 (Forward)',
        'qfmt': '{{Question}}',
        'afmt': '{{FrontSide}}<hr id="answer">{{Answer}}',
    },
    {
        'name': 'Card 2 (Reverse)',
        'qfmt': '{{Answer}}',
        'afmt': '{{FrontSide}}<hr id="answer">{{Question}}',
    },
]
```

#### 2b. Cloze -- `model_type=1` (CLOZE)

Cloze deletion cards hide parts of text using `{{cN::text}}` syntax. One Note can produce multiple Cards (one per unique cloze ordinal N).

```python
model = genanki.Model(
    1607892320,
    'Cloze Model',
    model_type=genanki.Model.CLOZE,   # or 1
    fields=[
        {'name': 'Text'},
        {'name': 'Extra'},            # second field required (even if empty)
    ],
    templates=[{
        'name': 'Cloze Card',
        'qfmt': '{{cloze:Text}}',
        'afmt': '{{cloze:Text}}<hr id="answer">{{Extra}}',
    }])

note = genanki.Note(
    model=model,
    fields=['{{c1::Rome}} is the capital of {{c2::Italy}}', ''])
```

This produces 2 cards:
- Card 1: "_____ is the capital of Italy" (answer: Rome)
- Card 2: "Rome is the capital of _____" (answer: Italy)

**Important:** The built-in `genanki.CLOZE_MODEL` is deprecated since v0.13.0. It previously had only one field, while Anki's real Cloze model has two. Create your own model with `model_type=1` instead.

---

### 3. Deck Organization

#### 3a. Single Deck

```python
my_deck = genanki.Deck(deck_id, 'My Deck Name')
my_deck.add_note(note1)
my_deck.add_note(note2)
```

#### 3b. Nested/Hierarchical Decks (Subdecks)

Anki supports hierarchical decks using `::` as a separator in the deck name. genanki handles this automatically:

```python
# Creates a hierarchy: Parent > Child
deck = genanki.Deck(2059400110, 'Parent::Child')

# Deeper nesting: Courses > Android > Interviews
deck = genanki.Deck(2059400111, 'Courses::Android::InterviewQuestions')
```

Anki will automatically create the parent decks in its UI.

#### 3c. Multiple Decks in One Package

```python
package = genanki.Package([deck1, deck2, deck3])
package.write_to_file('output.apkg')
```

---

### 4. Tags

Tags are set on individual notes via the `tags` parameter:

```python
note = genanki.Note(
    model=model,
    fields=['Question text', 'Answer text'],
    tags=['android', 'interview', 'activity-lifecycle'])
```

Tags are space-separated internally in the SQLite database (stored with leading/trailing spaces). genanki accepts a Python list of strings and joins them properly.

---

### 5. Best Practices

#### 5a. Stable IDs Are Critical

- **Model IDs** and **Deck IDs** must be unique integers, generated once and then **hardcoded** in the script.
- If the ID changes between imports, Anki creates a NEW deck/model instead of updating the existing one, breaking study progress.
- Generate IDs with: `import random; random.randrange(1 << 30, 1 << 31)`

#### 5b. Stable GUIDs for Notes

By default, a Note's GUID is a hash of ALL field values. If you add/change fields, the GUID changes, and Anki treats it as a new note (creating duplicates). Override with a custom GUID:

```python
class MyNote(genanki.Note):
    @property
    def guid(self):
        # Only hash the first field for stability
        return genanki.guid_for(self.fields[0])
```

#### 5c. Sort Field

- Controls the order notes appear in the Anki Browser.
- Default is the first field. Change with `sort_field_index=` on Model:
  ```python
  model = genanki.Model(..., sort_field_index=0)  # 0 = first field
  ```
- Or pass `sort_field=` to individual Notes.
- Avoid duplicate sort_field values (Anki "prefers" uniqueness but does not enforce it).

#### 5d. Media Files

To include images or audio:

```python
package = genanki.Package(my_deck)
package.media_files = ['images/diagram.png', 'audio/pronunciation.mp3']
```

Reference them in templates with:
- Images: `<img src="diagram.png">`
- Audio: `[sound:pronunciation.mp3]`
- Use only filenames (no paths) in the template references.

#### 5e. CSS Styling

Pass custom CSS to the model:

```python
model = genanki.Model(
    model_id,
    'Styled Model',
    fields=[...],
    templates=[...],
    css='''
        .card {
            font-family: "Noto Sans SC", "Helvetica Neue", sans-serif;
            font-size: 16px;
            line-height: 1.6;
        }
        .card.night_mode { color: #e0e0e0; }
    ''')
```

#### 5f. Card Order

All new cards are assigned `due=0` by genanki, meaning they all share the same "New #" in Anki's queue. To control display order:
- After import, use Anki's Browse > Reposition (start 0, step 1) to reorder.
- genanki does NOT have a built-in way to set custom due order (tracked in GitHub issue #75).

#### 5g. Field Values

- Field values are **HTML** -- you can include `<br>`, `<b>`, `<div>`, etc.
- The front side template (`qfmt`) must produce non-empty content, or no card is generated (the Note exists but is invisible in Anki).

---

### 6. .apkg Internal Format

An `.apkg` file is a **ZIP archive** containing:

```
my_deck.apkg
  +-- collection.anki2   (SQLite database, compressed with "deflate")
  +-- collection.anki21  (newer Anki versions; separate zstd-compressed)
  +-- media              (JSON mapping of int IDs to filenames: {"0": "image.png", "1": "audio.mp3"})
  +-- 0                  (media file, name is its integer ID)
  +-- 1                  (another media file)
  +-- meta               (format metadata, Protobuf in latest Anki)
```

#### SQLite Schema (collection.anki2 / collection.anki21)

Schema version: v11 (Legacy 2 format). Five main tables:

**`col` table** (single row -- collection-level config):
```sql
CREATE TABLE col (
    id     integer primary key,
    crt    integer not null,   -- creation timestamp (epoch days)
    mod    integer not null,   -- last modified (epoch seconds)
    scm    integer not null,   -- schema modification time
    ver    integer not null,   -- schema version (11 for v11)
    dty    integer not null,   -- dirty flag (unused, always 0)
    usn    integer not null,   -- update sequence number (for sync)
    ls     integer not null,   -- last sync time
    conf   text not null,      -- JSON: global preferences
    models text not null,      -- JSON: all model/notetype definitions
    decks  text not null,      -- JSON: all deck definitions
    dconf  text not null,      -- JSON: deck configuration
    tags   text not null       -- JSON: tag cache
);
```

**`notes` table** -- stores actual field content:
```sql
CREATE TABLE notes (
    id    integer primary key,  -- epoch ms timestamp
    guid  text not null,        -- globally unique ID (for deduplication)
    mid   integer not null,     -- model ID (key into col.models)
    mod   integer not null,     -- modification time
    usn   integer not null,     -- sync sequence
    tags  text not null,        -- space-separated, with leading/trailing space
    flds  text not null,        -- field values separated by 0x1f (unit separator char)
    sfld  integer not null,     -- sort field value (denormalized)
    csum  integer not null,     -- checksum for duplicate detection (SHA-1 first 8 hex digits)
    flags integer not null,     -- unused, always 0
    data  text not null         -- unused, always ''
);
```

**`cards` table** -- individual reviewable cards:
```sql
CREATE TABLE cards (
    id     integer primary key,  -- epoch ms timestamp
    nid    integer not null,     -- note ID (FK -> notes.id)
    did    integer not null,     -- deck ID (FK -> col.decks[id])
    ord    integer not null,     -- card ordinal within note (0 for first card)
    mod    integer not null,
    usn    integer not null,
    type   integer not null,     -- 0=new, 1=learning, 2=review, 3=relearning
    queue  integer not null,     -- -1=suspended, 0=new, 1=learning, 2=review, 3=day learning
    due    integer not null,     -- due date: queue-dependent
    ivl    integer not null,     -- interval (days)
    factor integer not null,     -- ease factor (2500 = 250%)
    reps   integer not null,     -- number of reviews
    lapses integer not null,     -- number of lapses
    left   integer not null,     -- remaining steps
    odue   integer not null,     -- original due (for filtered decks)
    odid   integer not null,     -- original deck ID (for filtered decks)
    flags  integer not null,
    data   text not null
);
```

**`revlog` table** -- immutable review history (immutable):
```sql
CREATE TABLE revlog (
    id     integer primary key,
    cid    integer not null,     -- card ID
    usn    integer not null,
    ease   integer not null,     -- 1=again, 2=hard, 3=good, 4=easy
    ivl    integer not null,     -- interval after review
    lastIvl integer not null,    -- interval before review
    factor integer not null,
    time   integer not null,     -- review time (ms)
    type   integer not null      -- 0=learning, 1=review, 2=relearning, 3=filtered
);
```

**`graves` table** -- tombstones for sync deletion:
```sql
CREATE TABLE graves (
    oid  integer not null,      -- original ID (card, note, or deck)
    type integer not null,      -- 0=card, 1=note, 2=deck
    usn  integer not null
);
```

#### Key Schema Insights

1. Fields in `notes.flds` are separated by the **unit separator** character `\x1f` (0x1F), not by newlines or commas.
2. The `media` file is a **JSON HashMap** mapping integer string keys to filenames: `{"0": "image.png", "1": "audio.mp3"}`.
3. Cards are fully pre-generated in the `.apkg` file -- Anki does NOT generate cards on import; it inserts the pre-made rows directly.
4. `csum = 0` is acceptable on write -- Anki recomputes it on import.
5. GUID matching is the sole deduplication mechanism on import. If the same GUID exists, the note is updated rather than duplicated.

#### APKG Format Versions

| Format | DB File | Schema | Compression | Config Storage |
|--------|---------|--------|-------------|----------------|
| Legacy 1 (Anki < 2.1) | `collection.anki2` | v11 | deflate | JSON in TEXT columns |
| Legacy 2 (Anki 2.1) | `collection.anki21` | v11 | zstd | JSON in TEXT columns |
| Latest (Anki 23+) | `collection.anki21b` | v18+ | zstd | Protobuf in BLOB columns |

genanki (v0.13.1) generates **Legacy 2 format** (collection.anki21 + compatibility collection.anki2), which is compatible with Anki 2.1+.

---

### 7. Alternative Libraries

| Library | Description | Strengths | Weaknesses |
|---------|-------------|-----------|------------|
| **genanki** | Python library for generating .apkg files | Mature, well-documented, simple API, PyPI package | No direct AnkiConnect support, limited to .apkg generation |
| **ankisync2** | ORM-based library (Peewee) for editing .anki2 / .apkg | Direct SQLite manipulation, full control over schema | More complex, less documentation, last updated 2021 |
| **anki-yaml-tool** | YAML-driven Anki deck builder with AnkiConnect push | Declarative config, supports push to running Anki | Requires genanki underneath, extra abstraction layer |
| **spacedrep** | CLI + MCP server for flashcards with FSRS scheduling | Full SRS engine, Anki-native schema, agent-friendly | Not focused on .apkg generation, more of a standalone SRS tool |
| **flashcore** | DuckDB-based SRS engine with FSRS | High performance, local-first, YAML authoring | Not Anki-compatible natively, different ecosystem |
| **deckgen** | AI-powered deck generation with generative AI | Auto-generates Q&A from content | Tied to OpenAI API, opinionated workflow |
| **anita-anki** | CSV-to-.apkg with TTS and illustrations | Multimedia support, language learning focus | Niche use case, uses genanki under the hood |

**Verdict:** For this project (PDF-to-Anki), **genanki is the best choice** due to:
- Mature and stable API
- Simple 4-step workflow (Model -> Note -> Deck -> Package)
- Direct .apkg output without requiring Anki to be installed
- Large community and many examples
- All alternative libraries either wrap genanki or are too opinionated/narrow

---

### 8. Key Limitations of genanki

1. **Card order control**: All new cards get `due=0`; no built-in way to set display order programmatically. Must reorder in Anki after import.
2. **No AnkiConnect integration**: genanki only generates .apkg files. It cannot push directly to a running Anki instance. AnkiConnect (a separate Anki addon) would be needed for that.
3. **Single-threaded ID generation**: Note and card IDs are generated from timestamps. If generating notes in tight loops across multiple decks, ID collisions can occur (fixed in v0.10.0+ by tracking a global counter).
4. **Requires stable IDs**: Model/Deck IDs and Note GUIDs must be predictable/sticky to enable re-import without duplicates.
5. **Anki compatibility**: genanki targets the Legacy 2 format. It may not be compatible with very old Anki versions (< 2.1) or handle future format changes until updated.

---

### 9. Project-Specific Notes

For the PDF-to-Anki task at hand:

- **Python PDF parsing**: genanki does not parse PDFs. A separate library (pymupdf, pdfplumber) is needed for text extraction.
- **Recommended model**: A Basic (Front/Back) model with fields `Question` and `Answer` is suitable for interview Q&A cards.
- **Suggested fields**: Consider adding an `Extra` or `Explanation` field for additional context, shown only on the back side.
- **Tags by category**: Use `tags` parameter on Notes to organize by Android topic (e.g., `['android', 'activity', 'lifecycle']`).
- **Deck hierarchy**: Use `::` separator, e.g., `Android::面试题` for the interview questions deck.

---

### Related Specs

- `/Users/mac/Documents/ai_workspace/anki_card_builder/.trellis/tasks/06-08-pdf-to-anki/prd.md` -- Project PRD specifying PDF-to-Anki conversion requirements.

### External References

- [genanki GitHub Repository](https://github.com/kerrickstaley/genanki) -- Main source, README docs
- [genanki on PyPI](https://pypi.org/project/genanki/) -- v0.13.1 package
- [genanki Usage Examples (DeepWiki)](https://deepwiki.com/kerrickstaley/genanki/6-usage-examples) -- Practical examples with code
- [Understanding the Anki APKG Format](https://eikowagenknecht.com/posts/understanding-the-anki-apkg-format/) -- Detailed format walkthrough
- [Anki Database Structure (AnkiDroid Wiki)](https://github.com/ankidroid/Anki-Android/wiki/Database-Structure) -- SQLite schema reference
- [Anki 2026 Database Structure (AnkiDroid Wiki)](https://github.com/ankidroid/Anki-Android/wiki/Database%E2%80%90Structure%E2%80%902026) -- Updated schema notes
- [Anki 2 Annotated Schema (gist)](https://gist.github.com/sartak/3921255) -- Community schema annotations
- [genanki apkg_schema.py](https://github.com/kerrickstaley/genanki/blob/main/genanki/apkg_schema.py) -- Direct source of SQL schema
- [Creating/Editing .apkg via SQLite](https://www.polv.cc/post/2019/07/anki-sqlite-edit) -- Blog post on manual SQLite editing
- [Cloze deletion support PR #37](https://github.com/kerrickstaley/genanki/pull/37) -- PR adding cloze support to genanki
- [Anki Forums: genanki card order issue](https://forums.ankiweb.net/t/genanki-can-not-get-the-card-order-right/58710) -- Community discussion on card ordering

## Caveats

- genanki v0.13.1 is the current latest version as of this writing. Always verify against PyPI for newer versions.
- The built-in `CLOZE_MODEL` has a deprecation warning in v0.13.0+. Use custom models with `model_type=1` instead.
- Anki's .apkg format has evolved (Legacy 1 -> Legacy 2 -> Latest). genanki targets Legacy 2, which is compatible with Anki 2.1+ but may not work with very old or very new Anki versions.
- The PDF parsing library choice (pymupdf vs pdfplumber) will significantly impact the quality of extracted text -- this is orthogonal to genanki.
