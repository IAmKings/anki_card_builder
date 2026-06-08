"""Interview PDF Parser (Regex-based).

Parses Android interview PDFs that already have Q&A format into flashcards.
"""

import logging
import re
from pathlib import Path
from typing import List

from ..models import Flashcard
from ..utils import extract_markdown, extract_tech_domain

log = logging.getLogger(__name__)


class InterviewPDFParser:
    """Parse the interview PDF which already has Q&A format."""

    def __init__(self, filepath: Path):
        self.filepath = filepath
        self.cards: List[Flashcard] = []

    def parse(self) -> List[Flashcard]:
        """Parse the interview PDF and extract Q&A pairs."""
        log.info(f"Parsing interview PDF: {self.filepath.name}")

        md_text = self._extract_markdown()
        self.cards = self._parse_qa_pairs(md_text)

        log.info(f"Extracted {len(self.cards)} Q&A pairs from interview PDF")
        return self.cards

    def _extract_markdown(self) -> str:
        return extract_markdown(self.filepath)

    def _parse_qa_pairs(self, md_text: str) -> List[Flashcard]:
        """Parse the markdown text into Q&A pairs with hierarchy."""
        cards: List[Flashcard] = []
        lines = md_text.split('\n')

        current_chapter = ""
        current_section = ""
        current_subsection = ""
        current_question = ""
        current_answer = ""
        in_answer = False

        chapter_pattern = re.compile(r'^#{0,4}\s*第[一二三四五六七八九十]+章\s*(.+)$')
        section_pattern = re.compile(r'^#{0,4}\s*第[一二三四五六七八九十]+节[、.．]\s*(.+)$')
        subsection_pattern = re.compile(r'^#{0,4}\s*[一二三四五六七八九十]+[、.．]\s*(.+?)(?:（.*?）)?$')
        question_pattern = re.compile(r'^(\d+)[、.．]\s*(.+)$')

        for line in lines:
            line = line.strip()
            if not line:
                if in_answer and current_answer:
                    current_answer += '\n'
                continue

            m = chapter_pattern.match(line)
            if m:
                if in_answer and current_question:
                    self._save_card(cards, current_chapter, current_section, current_subsection,
                                    current_question, current_answer)
                    current_question = ""
                    current_answer = ""
                    in_answer = False
                current_chapter = self._clean_header(m.group(1).strip())
                current_section = ""
                current_subsection = ""
                continue

            m = section_pattern.match(line)
            if m:
                if in_answer and current_question:
                    self._save_card(cards, current_chapter, current_section, current_subsection,
                                    current_question, current_answer)
                    current_question = ""
                    current_answer = ""
                    in_answer = False
                current_section = self._clean_header(m.group(1).strip())
                current_subsection = ""
                continue

            m = subsection_pattern.match(line)
            if m and len(line) < 30:
                subsection_text = m.group(1).strip()
                if not in_answer or (in_answer and len(current_answer) > 200):
                    if in_answer and current_question:
                        self._save_card(cards, current_chapter, current_section, current_subsection,
                                        current_question, current_answer)
                        current_question = ""
                        current_answer = ""
                        in_answer = False
                    current_subsection = self._clean_header(subsection_text)
                    continue

            m = question_pattern.match(line)
            if m:
                q_text = m.group(2).strip()
                is_list_item = (
                    in_answer and
                    len(q_text) < 30 and
                    not any(kw in q_text for kw in ['什么', '如何', '怎么', '为什么',
                                                     '哪些', '哪个', '是否',
                                                     '说说', '谈谈', '介绍', '了解'])
                )
                if not is_list_item:
                    if in_answer and current_question:
                        self._save_card(cards, current_chapter, current_section, current_subsection,
                                        current_question, current_answer)

                    current_question = q_text
                    current_answer = ""
                    in_answer = True
                else:
                    if current_answer:
                        current_answer += '\n' + line
                    else:
                        current_answer = line
                continue

            if in_answer:
                if current_answer:
                    current_answer += ' ' + line
                else:
                    current_answer = line

        if in_answer and current_question:
            self._save_card(cards, current_chapter, current_section, current_subsection,
                            current_question, current_answer)

        return cards

    def _clean_header(self, name: str) -> str:
        """Clean a chapter/section header by removing TOC artifacts."""
        name = re.sub(r'[\.\s]*\d+\s*$', '', name)
        name = re.sub(r'[\.\s]+$', '', name)
        return name.strip()

    def _save_card(self, cards: List[Flashcard], chapter: str, section: str,
                   subsection: str, question: str, answer: str):
        """Create a flashcard from a parsed Q&A pair and add to list."""
        chapter = self._clean_header(chapter)
        section = self._clean_header(section)
        subsection = self._clean_header(subsection)

        answer = answer.strip()
        if not answer or len(answer) < 5:
            return

        domain = extract_tech_domain(chapter=chapter, section=section, subsection=subsection)
        deck_name = f"Android面试::{domain}" if domain else "Android面试"

        section_parts = [p for p in [chapter, section, subsection] if p]
        source_section = " > ".join(section_parts) if section_parts else "未知章节"

        tags = ["android-interview"]
        tags.append(f"source:{Path(self.filepath).stem}")
        if domain:
            for part in domain.split("::"):
                tags.append(f"topic:{part}")

        card = Flashcard(
            front=question,
            back=answer,
            tags=tags,
            source_file=self.filepath.name,
            source_section=source_section,
            deck_name=deck_name,
            card_type="basic",
        )
        cards.append(card)
