"""Data models for flashcards."""

from dataclasses import dataclass, field
from typing import List

from .utils import sanitize_tag, clean_card_content


@dataclass
class Flashcard:
    """A single Anki flashcard."""
    front: str
    back: str
    tags: List[str] = field(default_factory=list)
    source_file: str = ""
    source_section: str = ""
    deck_name: str = "Android面试"
    card_type: str = "basic"  # "basic" or "cloze"

    def __post_init__(self):
        """Sanitize tags and clean content after initialization."""
        self.tags = [sanitize_tag(t) for t in self.tags]
        self.front = clean_card_content(self.front)
        self.back = clean_card_content(self.back)
