"""Knowledge PDF Parser (Heading-based + AI).

Parses knowledge reference PDFs like "Android 核心知识点笔记.pdf"
using heading-based splitting and optional AI answer generation.
"""

import json
import logging
import re
from pathlib import Path
from typing import List, Dict, Any

from ..config import CONFIG
from ..models import Flashcard
from ..utils import extract_markdown, is_toc_content, extract_tech_domain

log = logging.getLogger(__name__)


class KnowledgePDFParser:
    """Parse the knowledge reference PDF using heading-based splitting."""

    def __init__(self, filepath: Path):
        self.filepath = filepath
        self.cards: List[Flashcard] = []

    def parse(self) -> List[Flashcard]:
        """Parse the knowledge PDF and generate Q&A cards."""
        log.info(f"Parsing knowledge PDF: {self.filepath.name}")

        md_chunks = self._extract_markdown()
        sections = self._split_by_headings(md_chunks)
        log.info(f"Split into {len(sections)} sections")

        for i, section in enumerate(sections):
            cards = self._process_section(section)
            self.cards.extend(cards)

        log.info(f"Generated {len(self.cards)} cards from knowledge PDF")
        return self.cards

    def _extract_markdown(self) -> str:
        return extract_markdown(self.filepath)

    def _clean_section_title(self, title: str) -> str:
        title = re.sub(r'\*\*(.*?)\*\*', r'\1', title)
        title = title.replace('*', '')
        title = re.sub(r'^#+\s*', '', title)
        title = re.sub(r'^[、，,.\s]+', '', title)
        title = re.sub(r'[、，,]{2,}', '', title)
        return title.strip()

    def _split_by_headings(self, md_text: str) -> List[Dict[str, Any]]:
        """Split document into sections by Markdown headings."""
        sections = []

        try:
            import fitz
            doc = fitz.open(str(self.filepath))
            toc = doc.get_toc()
            doc.close()
        except Exception as e:
            log.warning(f"Could not read PDF TOC: {e}")
            toc = []

        if toc:
            lines = md_text.split('\n')
            current_section: Dict[str, Any] = {"title": "前言", "content": "", "level": 0, "breadcrumb": []}
            heading_pattern = re.compile(r'^(#{1,4})\s+(.+)$')

            for line in lines:
                m = heading_pattern.match(line)
                if m:
                    level = len(m.group(1))
                    title = self._clean_section_title(m.group(2).strip())

                    if current_section["content"].strip():
                        section_copy = current_section.copy()
                        section_copy["content"] = section_copy["content"].strip()
                        sections.append(section_copy)

                    breadcrumb = current_section["breadcrumb"][:]
                    if level <= current_section["level"]:
                        while breadcrumb and len(breadcrumb) >= level:
                            breadcrumb.pop()
                    breadcrumb.append(title)

                    current_section = {
                        "title": title,
                        "content": "",
                        "level": level,
                        "breadcrumb": breadcrumb.copy()
                    }
                else:
                    if current_section:
                        current_section["content"] += line + '\n'

            if current_section and current_section["content"].strip():
                sections.append(current_section)
        else:
            sections_raw = re.split(r'\n(?=#{1,4}\s)', md_text)
            for sec in sections_raw:
                lines = sec.split('\n')
                title_line = lines[0] if lines else ""
                m = re.match(r'^(#{1,4})\s+(.+)$', title_line)
                if m:
                    title = m.group(2).strip()
                    content = '\n'.join(lines[1:]).strip()
                else:
                    title = "前言"
                    content = sec.strip()

                if content:
                    sections.append({
                        "title": title,
                        "content": content,
                        "level": len(m.group(1)) if m else 0,
                        "breadcrumb": [title] if title else []
                    })

        sections = [s for s in sections if len(s["content"]) > 100]
        before = len(sections)
        sections = [s for s in sections if not is_toc_content(s["content"])]
        if len(sections) < before:
            log.debug(f"Filtered out {before - len(sections)} TOC/directory sections")

        return sections

    def _process_section(self, section: Dict) -> List[Flashcard]:
        """Process a single section and generate flashcards."""
        title = section["title"]
        content = section["content"]
        breadcrumb = section.get("breadcrumb", [title])

        if CONFIG.api_key:
            try:
                ai_cards = self._generate_with_claude(title, content, breadcrumb)
                if ai_cards:
                    return ai_cards
            except Exception as e:
                log.warning(f"AI generation failed for section '{title}': {e}")
                log.warning("Falling back to content-based extraction")

        cards = self._extract_basic_cards(title, content, breadcrumb)
        return cards

    def _generate_with_claude(self, title: str, content: str, breadcrumb: List[str]) -> List[Flashcard]:
        """Use Claude API to generate Q&A cards from a section."""
        from anthropic import Anthropic

        client = Anthropic(api_key=CONFIG.api_key)

        breadcrumb_str = " > ".join(breadcrumb)
        source_name = self.filepath.name

        prompt = f"""你是一个专业的 Anki 卡片制作专家。请根据以下 Android 技术资料内容，生成高质量的问答卡片。

来源文件: {source_name}
章节: {breadcrumb_str}

内容:
{content[:4000]}

要求:
1. 生成 3-8 张问答卡片，每张卡片只测试一个知识点
2. 问题要清晰明确，答案要准确完整
3. 避免"是/否"类问题
4. 如果内容适合出选择题或填空题，请标注卡片类型为"cloze"
5. 为每张卡片添加技术标签

请以 JSON 格式输出，格式如下:
{{
  "cards": [
    {{
      "front": "问题",
      "back": "答案",
      "tags": ["标签1", "标签2"],
      "card_type": "basic"
    }}
  ]
}}

只输出 JSON，不要包含其他内容。"""

        response = client.messages.create(
            model=CONFIG.api_model,
            max_tokens=4000,
            temperature=0.3,
            messages=[{"role": "user", "content": prompt}]
        )

        result = response.content[0].text

        try:
            json_match = re.search(r'\{[\s\S]*\}', result)
            if json_match:
                data = json.loads(json_match.group())
            else:
                data = json.loads(result)

            cards_data = data.get("cards", data if isinstance(data, list) else [])

            cards = []
            domain = extract_tech_domain(section=" ".join(breadcrumb))
            deck_name = f"Android面试::{domain}" if domain else "Android面试"

            for item in cards_data:
                front = item.get("front", "").strip()
                back = item.get("back", "").strip()
                if not front or not back:
                    continue

                tags = item.get("tags", [])
                if isinstance(tags, str):
                    tags = [tags]
                tags.extend([
                    f"source:{Path(self.filepath).stem}",
                    "ai-generated"
                ])

                card = Flashcard(
                    front=front,
                    back=back,
                    tags=tags,
                    source_file=source_name,
                    source_section=breadcrumb_str,
                    deck_name=deck_name,
                    card_type=item.get("card_type", "basic"),
                )
                cards.append(card)

            return cards

        except (json.JSONDecodeError, KeyError) as e:
            log.warning(f"Failed to parse AI response for '{title}': {e}")
            return []

    def _extract_basic_cards(self, title: str, content: str, breadcrumb: List[str]) -> List[Flashcard]:
        """Fallback: extract key information as basic cards."""
        cards = []
        source_name = self.filepath.name
        breadcrumb_str = " > ".join(breadcrumb)
        domain = extract_tech_domain(section=" ".join(breadcrumb))
        deck_name = f"Android面试::{domain}" if domain else "Android面试"

        tags = [
            f"source:{Path(self.filepath).stem}",
            "extracted",
        ]
        for part in domain.split("::") if domain else []:
            tags.append(f"topic:{part}")

        skip_titles = {"目录", "前言", "附录", "参考文献", "索引"}
        clean_title = re.sub(r'^[\d\s.．、\-]+', '', title).strip()
        if not clean_title:
            clean_title = title.strip()
        if clean_title in skip_titles:
            return []
        title = clean_title

        clean_content = content
        clean_content = re.sub(r'^#{1,4}\s+', '', clean_content, flags=re.MULTILINE)
        clean_content = re.sub(r'<[^>]+>', '', clean_content)
        clean_content = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', clean_content)
        clean_content = re.sub(r'\s+', ' ', clean_content)
        clean_content = clean_content.strip()
        if len(clean_content) < 20:
            return []

        sentences = re.split(r'(?<=[。！？.!?])\s*', clean_content)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 15]

        definition_keywords = ['是指', '指的是', '即', '就是', '表示', '称为', '叫做',
                               '意思', '定义', '本质', '指', '可分为', '主要用于',
                               '指的是', '意思就是说']
        for sent in sentences[:8]:
            has_def = any(kw in sent for kw in definition_keywords)
            if has_def and len(sent) < 400:
                for kw in definition_keywords:
                    if kw in sent:
                        parts = sent.split(kw, 1)
                        raw_term = parts[0].strip().rstrip('，, ')
                        defn = parts[1].strip()

                        term = re.sub(r'^[\d\s.．、]+', '', raw_term).strip()
                        if not term:
                            term = raw_term

                        if (5 < len(term) < 60 and len(defn) > 10
                                and not term.isdigit()
                                and not term.startswith('第')):
                            front = f"什么是{term}？"
                            cards.append(Flashcard(
                                front=front,
                                back=defn,
                                tags=tags,
                                source_file=source_name,
                                source_section=breadcrumb_str,
                                deck_name=deck_name,
                                card_type="basic",
                            ))
                            break

        if len(cards) < 2:
            existing_backs = {c.back[:50] for c in cards}
            for sent in sentences:
                sent = sent.strip()
                if len(sent) < 30 or len(sent) > 500:
                    continue
                if re.match(r'^[\d\s/\-—|\\]+$', sent):
                    continue
                if sent[:50] in existing_backs:
                    continue
                chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', sent))
                if chinese_chars < 10:
                    continue

                first_term_match = re.match(r'^([\u4e00-\u9fff]{2,20})[是叫称为指即]', sent)
                if first_term_match:
                    term = first_term_match.group(1)
                    cards.append(Flashcard(
                        front=f"什么是{term}？",
                        back=sent,
                        tags=tags,
                        source_file=source_name,
                        source_section=breadcrumb_str,
                        deck_name=deck_name,
                        card_type="basic",
                    ))
                    existing_backs.add(sent[:50])
                elif len(cards) < 1:
                    front = f"{title}知识点：{sent[:30]}..."
                    cards.append(Flashcard(
                        front=front,
                        back=sent,
                        tags=tags,
                        source_file=source_name,
                        source_section=breadcrumb_str,
                        deck_name=deck_name,
                        card_type="basic",
                    ))
                    existing_backs.add(sent[:50])

                if len(cards) >= 3:
                    break

        return cards
