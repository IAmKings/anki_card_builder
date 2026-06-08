"""TXT File Parser.

Parses plain text files containing interview questions and generates
Q&A flashcards with optional AI-powered answer generation.
"""

import logging
import re
from pathlib import Path
from typing import List, Dict

from ..config import CONFIG
from ..models import Flashcard
from ..utils import extract_tech_domain

log = logging.getLogger(__name__)


class TxtParser:
    """Parse TXT files and generate Q&A cards with AI."""

    def __init__(self, filepath: Path):
        self.filepath = filepath
        self.cards: List[Flashcard] = []

    def parse(self) -> List[Flashcard]:
        """Parse a text file and generate cards."""
        log.info(f"Parsing TXT file: {self.filepath.name}")

        questions = self._read_questions()
        log.info(f"Read {len(questions)} questions from {self.filepath.name}")

        for q_data in questions:
            cards = self._process_question(q_data)
            self.cards.extend(cards)

        log.info(f"Generated {len(self.cards)} cards from {self.filepath.name}")
        return self.cards

    def _read_questions(self) -> List[Dict]:
        """Read questions from the text file."""
        text = self._read_file()
        lines = text.strip().split('\n')

        questions = []
        current_category = ""
        current_question = ""

        category_pattern = re.compile(r'^([\u4e00-\u9fff\w]+)[：:]')
        question_pattern = re.compile(r'^\s*(\d+)[、.．]\s*(.*)')
        sub_item_pattern = re.compile(r'^\s+(\d+)[、.．]\s+(.*)')

        for line in lines:
            line = line.strip()
            if not line:
                continue

            m = category_pattern.match(line)
            if m and len(line) < 30:
                current_category = m.group(1)
                continue

            m = sub_item_pattern.match(line)
            if m:
                continue

            m = question_pattern.match(line)
            if m:
                q_text = m.group(2).strip()
                if q_text:
                    questions.append({
                        "text": q_text,
                        "number": m.group(1),
                        "category": current_category
                    })
                continue

            if len(line) > 5 and not line.startswith('(') and not line.startswith('（'):
                if current_question:
                    current_question += " " + line
                else:
                    current_question = line

        if current_question and len(current_question) > 5:
            questions.append({
                "text": current_question,
                "number": "",
                "category": current_category
            })

        return questions

    def _read_file(self) -> str:
        """Read file with encoding detection."""
        raw = self.filepath.read_bytes()

        for enc in ['utf-8', 'gbk', 'gb2312', 'gb18030']:
            try:
                return raw.decode(enc)
            except UnicodeDecodeError:
                continue

        return raw.decode('gbk', errors='replace')

    def _process_question(self, q_data: Dict) -> List[Flashcard]:
        """Process a single question and generate cards."""
        q_text = q_data["text"]
        category = q_data.get("category", "")

        if CONFIG.api_key:
            try:
                ai_cards = self._generate_with_claude(q_text, category)
                if ai_cards:
                    return ai_cards
            except Exception as e:
                log.warning(f"AI generation failed for question '{q_text[:30]}...': {e}")

        return self._create_basic_card(q_text, category)

    def _generate_with_claude(self, question: str, category: str) -> List[Flashcard]:
        """Use Claude API to generate an answer for a question."""
        from anthropic import Anthropic

        client = Anthropic(api_key=CONFIG.api_key)
        source_name = self.filepath.name

        prompt = f"""你是一个 Android 开发面试专家。请回答以下面试题。

来源: {source_name}
分类: {category}
题目: {question}

请给出一个详细、准确的答案，适合用作 Anki 闪卡。答案应该：
1. 准确全面，覆盖关键知识点
2. 结构清晰（可以用要点形式）
3. 适合面试回答
4. 长度适中（100-500字）

只输出答案内容，不要包含额外说明。"""

        response = client.messages.create(
            model=CONFIG.api_model,
            max_tokens=2000,
            temperature=0.3,
            messages=[{"role": "user", "content": prompt}]
        )

        answer = response.content[0].text.strip()
        if not answer or len(answer) < 10:
            return []

        domain = extract_tech_domain(section=category, subsection=question)
        deck_name = f"Android面试::{domain}" if domain else "Android面试"

        card = Flashcard(
            front=question,
            back=answer,
            tags=[
                f"source:{Path(self.filepath).stem}",
                "ai-generated",
                f"topic:{domain.split('::')[0] if domain else '其他'}",
            ],
            source_file=source_name,
            source_section=category or "未知分类",
            deck_name=deck_name,
            card_type="basic",
        )
        return [card]

    def _create_basic_card(self, question: str, category: str) -> List[Flashcard]:
        """Create a basic card with the question and a placeholder answer."""
        domain = extract_tech_domain(section=category, subsection=question)
        deck_name = f"Android面试::{domain}" if domain else "Android面试"

        placeholder_answer = f"【待补充答案】\n\n来源：{self.filepath.name}\n分类：{category}\n\n此问题来自 {self.filepath.name}，答案需要补充。请参考相关资料完善此卡片。"

        card = Flashcard(
            front=question,
            back=placeholder_answer,
            tags=[
                f"source:{Path(self.filepath).stem}",
                "pending",
                f"topic:{domain.split('::')[0] if domain else '其他'}",
            ],
            source_file=self.filepath.name,
            source_section=category or "未知分类",
            deck_name=deck_name,
            card_type="basic",
        )
        return [card]
