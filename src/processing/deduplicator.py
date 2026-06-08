"""Deduplication module for flashcards."""

import logging
from typing import List

from ..models import Flashcard
from ..utils import similarity

log = logging.getLogger(__name__)


class Deduplicator:
    """Deduplicate flashcards across sources."""

    def __init__(self, threshold: float = 0.85):
        self.threshold = threshold

    def deduplicate(self, cards: List[Flashcard]) -> List[Flashcard]:
        """Remove duplicate cards, merging source info for duplicates."""
        if not cards:
            return []

        log.info(f"Deduplicating {len(cards)} cards (threshold: {self.threshold})")

        unique_cards: List[Flashcard] = []

        for card in cards:
            is_dup = False
            for existing in unique_cards:
                if similarity(card.front, existing.front) > self.threshold:
                    is_dup = True
                    existing.tags = list(set(existing.tags + card.tags))
                    existing.source_section += f" | also in: {card.source_section}"
                    if len(card.back) > len(existing.back):
                        existing.back = card.back
                    log.debug(f"Duplicate found: '{card.front[:30]}...' matches '{existing.front[:30]}...'")
                    break

            if not is_dup:
                unique_cards.append(card)

        duplicates_removed = len(cards) - len(unique_cards)
        log.info(f"Removed {duplicates_removed} duplicates, {len(unique_cards)} unique cards remain")

        return unique_cards

    @staticmethod
    def deduplicate_dicts(cards: List[dict], threshold: float = 0.85) -> List[dict]:
        """Deduplicate dict-based cards (from rebuild_apkg.py compatibility)."""
        import re
        from difflib import SequenceMatcher

        def normalize(s: str) -> str:
            return re.sub(r'[^\w\u4e00-\u9fff]', '', s).lower()

        unique = []
        for card in cards:
            is_dup = False
            nf = normalize(card.get('front', ''))
            for existing in unique:
                ne = normalize(existing.get('front', ''))
                if SequenceMatcher(None, nf, ne).ratio() > threshold:
                    existing_tags = set(existing.get('tags', []))
                    new_tags = set(card.get('tags', []))
                    existing['tags'] = list(existing_tags | new_tags)
                    src = card.get('source', '')
                    if src and src not in existing.get('source', ''):
                        existing['source'] = existing.get('source', '') + ' | ' + src
                    is_dup = True
                    break
            if not is_dup:
                unique.append(card)
        return unique
