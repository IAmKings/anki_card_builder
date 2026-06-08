"""Quality filter module for flashcards."""

import logging
import re
from typing import List, Dict

from ..models import Flashcard

log = logging.getLogger(__name__)


class QualityFilter:
    """Filter and validate flashcards."""

    @staticmethod
    def validate(cards: List[Flashcard]) -> List[Flashcard]:
        """Remove invalid or low-quality cards."""
        valid = []

        for card in cards:
            if not card.front or len(card.front.strip()) < 5:
                continue
            if not card.back or len(card.back.strip()) < 5:
                continue
            if card.front.strip().isdigit():
                continue

            special_ratio = sum(1 for c in card.front if c in '*#$%^&') / max(len(card.front), 1)
            if special_ratio > 0.3:
                continue
            if card.back == "【待补充答案】":
                continue
            if re.match(r'^(什么是)?\d+\s+\S', card.front) and len(card.front) < 30:
                continue
            if re.search(r'(?:被？|为？)$', card.front):
                continue
            if len(card.front.strip()) < 5:
                continue
            if len(card.front.replace('？', '').replace('?', '').strip()) < 5:
                continue
            if re.search(r'^什么是[这那]个', card.front):
                continue
            if re.search(r'[是就有]？$', card.front):
                continue

            chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', card.front))
            if chinese_chars < 2 and len(card.front) > 10:
                continue

            valid.append(card)

        removed = len(cards) - len(valid)
        if removed:
            log.info(f"Quality filter removed {removed} invalid cards")

        return valid

    @staticmethod
    def validate_dicts(cards: List[Dict]) -> List[Dict]:
        """Validate dict-based cards (from rebuild_apkg.py compatibility)."""
        valid = []
        for card in cards:
            front = card.get('front', '')
            back = card.get('back', '')
            ctype = card.get('card_type', 'basic')

            if ctype == 'cloze':
                if not re.search(r'\{\{c\d+::.+?\}\}', front):
                    continue
                valid.append(card)
                continue

            chinese_front = len(re.findall(r'[\u4e00-\u9fff]', front))
            if chinese_front < 5:
                continue
            chinese_back = len(re.findall(r'[\u4e00-\u9fff]', back))
            if chinese_back < 10:
                continue

            bad = ['以下说法正确的是', '简述：', '什么是对于', '什么是3 ']
            if any(p in front for p in bad):
                continue

            valid.append(card)
        return valid
