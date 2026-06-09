"""Kotlin Markdown Parser.

Parses Kotlin coroutine Q&A markdown files (e.g., "Kotlin 协程深入的 100 道题")
into flashcards. This was previously in generate_kotlin_cards.py.
"""

import json
import logging
import re
from pathlib import Path
from typing import List, Dict

from ..models import Flashcard

log = logging.getLogger(__name__)


class KotlinMDParser:
    """Parse Kotlin coroutine markdown Q&A files into flashcards."""

    def __init__(self, filepath: Path):
        self.filepath = filepath

    def parse(self) -> List[Flashcard]:
        """Parse markdown file and return flashcards."""
        log.info(f"Parsing Kotlin MD: {self.filepath.name}")
        cards_data = self._parse_md()
        cards = []
        source_stem = Path(self.filepath).stem
        for item in cards_data:
            card = Flashcard(
                front=item["front"],
                back=item["back"],
                tags=item.get("tags", ["Kotlin", "协程"]),
                source_file=self.filepath.name,
                source_section=item.get("source", ""),
                deck_name="Android面试::Kotlin",
                card_type=item.get("card_type", "basic"),
            )
            cards.append(card)
        log.info(f"Extracted {len(cards)} cards from {self.filepath.name}")
        return cards

    def parse_to_dict(self) -> List[Dict]:
        """Parse and return dicts (for JSON export compatibility)."""
        return self._parse_md()

    def _parse_md(self) -> List[Dict]:
        """Parse markdown file and extract Q&A pairs."""
        with open(str(self.filepath), 'r', encoding='utf-8') as f:
            text = f.read()

        cards = []
        section = "综合"

        blocks = re.split(r'\n(?=### \*\*\d+\\\. )', text)

        for block in blocks:
            sec = re.search(r'## \*\*(.+?)\*\*', block)
            if sec:
                s = sec.group(1)
                if '基础' in s or '设计' in s:
                    section = "基础与设计哲学"
                elif '上下文' in s or '调度' in s:
                    section = "上下文与调度器"
                elif '生命周期' in s or '取消' in s:
                    section = "生命周期与取消"
                elif '异常' in s or '并发安全' in s:
                    section = "异常处理与并发安全"
                elif 'Channel' in s:
                    section = "Channel管道"
                elif 'Flow 全家桶' in s or '核心原理' in s:
                    section = "Flow核心原理"
                elif '状态流' in s or 'StateFlow' in s or 'SharedFlow' in s:
                    section = "SharedFlow与StateFlow"
                elif '背压' in s or 'Backpressure' in s:
                    section = "背压处理"
                elif 'Android' in s or '实战' in s or 'Jetpack' in s:
                    section = "Android实战"
                elif '测试' in s:
                    section = "测试与调试"
                elif '源码' in s:
                    section = "源码分析"

            qm = re.match(r'### \*\*\d+\\\.\s*(.+?)\*\*', block)
            if not qm:
                continue
            question = qm.group(1).strip()

            am = re.search(r'\*\*确切答案[：:]\*\*\s*(.+?)(?=\n(?:### \*\*|\n## \*\*|\n\*\*提示|\Z))', block, re.DOTALL)
            if not am:
                continue
            answer = am.group(1).strip()

            # Clean answer formatting (ORDER MATTERS!)
            # 1. Clean escaped chars first
            answer = answer.replace('\\*', '')
            answer = answer.replace('\\-', '-')
            answer = answer.replace('\\>', '>')
            answer = answer.replace('\\<', '<')
            answer = answer.replace('\\=', '=')
            # 2. Convert markdown bold to HTML bold
            answer = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', answer)
            # 3. Strip leading bullet (after escape cleanup)
            answer = re.sub(r'^\*\s*', '', answer)
            # 4. Convert inner bullet points: "\n  * text" → "<br>• text"
            answer = re.sub(r'\n\s*\*\s+', '<br>• ', answer)
            # 5. Convert numbered items: "\n  1. text" → "<br>1. text"
            answer = re.sub(r'\n\s+(\d+)\\.\s+', r'<br>\1. ', answer)
            # 6. Compress blank lines
            answer = re.sub(r'\n{3,}', '<br><br>', answer)
            answer = re.sub(r'\n', '<br>', answer)
            # 7. Collapse multiple <br> tags
            answer = re.sub(r'(<br>\s*){3,}', '<br><br>', answer)
            # 8. Compress spaces and strip
            answer = re.sub(r'  +', ' ', answer)
            answer = answer.strip()
            # 9. Limit length
            if len(answer) > 3000:
                answer = answer[:3000] + '...'

            cards.append({
                "front": question,
                "back": answer,
                "card_type": "basic",
                "tags": ["Kotlin", "协程", section],
                "source": f"Kotlin 协程深入的 100 道题 > {section}"
            })

        return cards
