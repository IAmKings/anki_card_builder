"""通用 Markdown Q&A 解析器。

支持多种 MD Q&A 格式：
- 问题：### / #### / ##### **N. text** 或 **N\. text**
- 答案：**确切答案：** / **答案：** / 确切答案：
"""
import logging
import re
from pathlib import Path
from typing import List, Dict

from ..models import Flashcard

log = logging.getLogger(__name__)


class KotlinMDParser:
    """通用 MD Q&A 解析器，支持多种格式。"""

    def __init__(self, filepath: Path):
        self.filepath = filepath

    def parse(self) -> List[Flashcard]:
        log.info(f"Parsing Markdown: {self.filepath.name}")
        cards_data = self._parse_md()
        cards = []
        for item in cards_data:
            card = Flashcard(
                front=item["front"],
                back=item["back"],
                tags=item.get("tags", []),
                source_file=self.filepath.name,
                source_section=item.get("source", ""),
                deck_name=item.get("deck_name", "Android面试"),
                card_type=item.get("card_type", "basic"),
            )
            cards.append(card)
        log.info(f"Extracted {len(cards)} cards from {self.filepath.name}")
        return cards

    def parse_to_dict(self) -> List[Dict]:
        return self._parse_md()

    def _detect_deck(self) -> str:
        """根据文件名推断牌组"""
        name = self.filepath.name.lower()
        if 'kotlin' in name or '协程' in name:
            return "Android面试::Kotlin"
        if 'java' in name or 'jvm' in name:
            return "Android面试::Java"
        if '阿里巴巴' in name:
            return "Android面试::阿里巴巴真题"
        if '高频核心' in name:
            return "Android面试::高频题集"
        return "Android面试::综合"

    def _detect_topic(self, section_title: str) -> str:
        """从章节标题提取主题标签"""
        s = section_title.lower()
        if any(k in s for k in ['java', 'jvm', '并发', '线程', '锁', '集合', '泛型', '反射']):
            return "Java"
        if any(k in s for k in ['android', 'activity', 'service', 'fragment', 'view',
                                  'handler', 'binder', 'ipc', '组件', 'ui']):
            return "Android"
        if any(k in s for k in ['kotlin', '协程', 'flow', 'channel', 'suspend']):
            return "Kotlin"
        if any(k in s for k in ['网络', 'http', 'tcp', 'socket', 'retrofit', 'okhttp']):
            return "网络"
        if any(k in s for k in ['算法', '数据', '排序', '树', '图', '链表']):
            return "算法"
        if any(k in s for k in ['设计模式', '架构', 'mvc', 'mvp', 'mvvm']):
            return "设计模式"
        if any(k in s for k in ['性能', '优化', '内存', '泄漏', '启动']):
            return "性能优化"
        if any(k in s for k in ['系统', '底层', 'framework', 'ndk', '源码']):
            return "系统底层"
        if any(k in s for k in ['compose', 'jetpack', 'modern']):
            return "现代化开发"
        return "综合"

    def _parse_md(self) -> List[Dict]:
        with open(str(self.filepath), 'r', encoding='utf-8') as f:
            text = f.read()

        cards = []
        current_section = "综合"
        deck_name = self._detect_deck()

        # Split by question markers - try 3 formats:
        # Format A: ### / #### / ##### **N\. text** (bold heading)
        # Format B: **N\. text** (bold, no heading marker)
        # Format C: ### / #### / ##### N. text (plain heading, no bold)
        blocks = re.split(r'\n(?=#{3,6} \*\*\d+\S+\s)', text)
        if len(blocks) <= 2:
            blocks = re.split(r'\n(?=\*\*\d+\S+\s)', text)
        if len(blocks) <= 2:
            blocks = re.split(r'\n(?=#{2,4} \d+\S+\s)', text)

        for block in blocks:
            # Track section changes from ## or ### section headers
            sec = re.search(r'#{2,3} \*\*(.+?)\*\*', block)
            if sec:
                current_section = sec.group(1).strip()

            # Extract question - try 3 formats
            qm = re.match(r'#{3,6} \*\*\d+\S+\s*(.+?)\*\*', block)  # A: bold heading
            if not qm:
                qm = re.match(r'\*\*\d+\S+\s*(.+?)\*\*', block)      # B: bold-numbered
            if not qm:
                qm = re.match(r'#{2,4} \d+[\.\、\s]+(.+)', block)    # C: plain heading
                if qm:
                    question = qm.group(1).strip()
                else:
                    continue
            else:
                question = qm.group(1).strip()
            # Clean question text of markdown escapes
            question = question.replace('\\', '')

            # Extract answer - try explicit markers first, then inline
            answer = None
            for pattern in [
                r'\*?\s*\*\*确切答案\*\*[：:]\s*(.+)',
                r'\*?\s*\*\*答案\*\*[：:]\s*(.+)',
                r'\*?\s*\*\*确切答案[：:]\*\*\s*(.+)',
                r'\*?\s*\*\*答案[：:]\*\*\s*(.+)',
                r'\*?\s*确切答案[：:]\s*(.+)',
            ]:
                am = re.search(pattern, block, re.DOTALL)
                if am:
                    answer = am.group(1).strip()
                    answer = re.split(r'\n(?:#{2,3} \*\*[^\d])', answer)[0]
                    answer = re.split(r'\n\*{0,2}[祝欢谢谢]', answer)[0]
                    break

            # Inline answer: everything after the heading line, until next heading or code block start
            if not answer:
                # Find content after the heading match
                content_start = qm.end()
                rest = block[content_start:].strip()
                # Trim at next heading or "---" separator
                rest = re.split(r'\n(?:#{2,4} |---)', rest)[0]
                if len(rest) > 20:
                    answer = rest

            if not answer:
                continue

            # ============================================================
            # Clean answer formatting
            # ============================================================
            answer = self._clean_answer(answer)

            topic = self._detect_topic(current_section)
            cards.append({
                "front": question,
                "back": answer,
                "card_type": "basic",
                "tags": [topic, self._detect_topic(self.filepath.name)],
                "deck_name": deck_name,
                "source": f"{self.filepath.name} > {current_section}"
            })

        return cards

    def _clean_answer(self, answer: str) -> str:
        """统一的答案格式清理"""
        # 1. Clean escaped chars - twice to catch nested escapes like \\<
        for ch in ['*', '-', '>', '<', '=', '/', '_']:
            answer = answer.replace(f'\\{ch}', ch)
        # Second pass for any remaining escapes (e.g., \> inside angle brackets)
        answer = answer.replace('\\>', '>')
        answer = answer.replace('\\<', '<')

        # 2. Convert code blocks: ```lang\n code \n``` → <pre><code>
        def convert_code(m):
            code = m.group(1).strip()
            return f'<pre><code>{code}</code></pre>'
        answer = re.sub(r'```\w*\n(.+?)```', convert_code, answer, flags=re.DOTALL)

        # 3. Convert markdown bold to HTML bold
        answer = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', answer)

        # 3. Strip leading bullet
        answer = re.sub(r'^\*\s*', '', answer)

        # 4. Convert inner bullets: "\n  * text" → "<br>• text"
        answer = re.sub(r'\n\s*\*\s+', '<br>• ', answer)

        # 5. Convert numbered items
        answer = re.sub(r'\n\s+(\d+)\\\.\s+', r'<br>\1. ', answer)

        # 6. Newlines → <br>
        answer = re.sub(r'\n{3,}', '<br><br>', answer)
        answer = re.sub(r'\n', '<br>', answer)

        # 7. Collapse excessive <br> tags
        answer = re.sub(r'(<br>\s*){3,}', '<br><br>', answer)

        # 8. Compress spaces
        answer = re.sub(r'  +', ' ', answer)
        answer = answer.strip()

        # 9. Limit length
        if len(answer) > 3000:
            answer = answer[:3000] + '...'

        return answer
