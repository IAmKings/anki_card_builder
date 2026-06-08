#!/usr/bin/env python3
"""
PDF-to-Anki Card Builder Pipeline
Converts Android interview PDFs and txt files into Anki flashcards (.apkg)

Usage:
    python3 main.py

Requires:
    - ANTHROPIC_API_KEY environment variable (for AI-powered generation)
    - pymupdf4llm, genanki, anthropic packages

Architecture:
    1. Extract: pymupdf4llm to Markdown
    2. Structure Analysis: regex for interview PDF / heading split for knowledge PDF
    3. AI Generation: Claude API for knowledge PDF + txt answer generation
    4. Quality Filter: validate + deduplicate
    5. Export: genanki .apkg with hierarchical decks
"""

import re
import os
import json
import hashlib
import logging
import sys
from pathlib import Path
from difflib import SequenceMatcher
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass, field

import genanki

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
log = logging.getLogger(__name__)

# =============================================================
# Configuration
# =============================================================

@dataclass
class Config:
    """Pipeline configuration."""
    data_dir: Path = Path("data")
    output_dir: Path = Path("output")
    output_file: str = "Android面试卡组.apkg"

    # genanki model/deck IDs (generate once, then hardcode for stability)
    basic_model_id: int = 1607392319
    cloze_model_id: int = 1607892320
    parent_deck_id: int = 2059400110

    # Deduplication threshold
    dedup_threshold: float = 0.85

    # Minimum cards per PDF
    min_cards_per_pdf: int = 100

    # API configuration
    api_key: str = field(default_factory=lambda: os.environ.get("ANTHROPIC_API_KEY", ""))
    api_model: str = "claude-sonnet-4-20250514"


# Global config
CONFIG = Config()


# =============================================================
# Data Models
# =============================================================

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


# =============================================================
# Utility Functions
# =============================================================

def normalize_text(text: str) -> str:
    """Normalize text for comparison (remove punctuation, extra spaces)."""
    text = re.sub(r'[^\u4e00-\u9fff\w]', '', text)  # keep Chinese chars + alphanumeric
    return text.strip().lower()


def sanitize_tag(tag: str) -> str:
    """Sanitize a tag value so it doesn't contain spaces (genanki requirement)."""
    # Replace spaces and special chars with underscores
    tag = re.sub(r'[\s/\\:;&@#$%^*()+=<>{}|~]+', '_', tag)
    # Remove leading/trailing underscores
    tag = tag.strip('_')
    # Remove consecutive underscores
    tag = re.sub(r'_+', '_', tag)
    return tag if tag else "untagged"


def similarity(a: str, b: str) -> float:
    """Compute text similarity using difflib."""
    return SequenceMatcher(None, normalize_text(a), normalize_text(b)).ratio()


def extract_tech_domain(chapter: str = "", section: str = "", subsection: str = "") -> str:
    """Extract the tech domain for deck hierarchy and tags.

    Maps chapter/section names to predefined tech domains.
    Matches against combined context from chapter, section, and subsection.
    """
    text = (chapter + " " + section + " " + subsection).lower()
    # Remove noise words that appear in all interview chapter names
    for noise in ["面试题", "面试", "（", "）", "( )", "⭐", "试题"]:
        text = text.replace(noise, "")

    # Java & JVM
    if any(kw in text for kw in ["jvm", "虚拟机", "类加载", "垃圾回收", "gc", "内存模型",
                                  "运行时数据", "字节码", "堆栈"]):
        return "Java::JVM"

    if any(kw in text for kw in ["java", "面向对象", "多态", "抽象", "接口",
                                  "内部类", "集合", "框架", "泛型", "反射",
                                  "注解", "动态代理", "单例", "设计模块",
                                  "string", "异常", "关键字", "static",
                                  "final", "引用类型"]):
        if any(kw in text for kw in ["集合", "hashmap", "concurrent", "arraylist",
                                      "linkedlist", "map"]):
            return "Java::集合"
        if any(kw in text for kw in ["反射", "动态代理", "注解"]):
            return "Java::高级特性"
        return "Java"

    # Java Concurrency
    if any(kw in text for kw in ["并发", "多线程", "线程", "锁", "synchronized",
                                  "volatile", "thread", "线程池", "aqs",
                                  "reentrantlock", "cas", "copyonwrite",
                                  "countdownlatch", "cyclicbarrier"]):
        return "Java::并发"

    # Network
    if any(kw in text for kw in ["网络", "http", "tcp", "udp", "https", "dns",
                                  "ssl", "tls", "socket", "ip地址", "抓包",
                                  "okhttp", "retrofit", "websocket",
                                  "quic", "cdn"]):
        if any(kw in text for kw in ["tcp", "udp", "三次握手", "四次挥手", "滑动窗口",
                                      "拥塞控制"]):
            return "网络::TCP"
        if any(kw in text for kw in ["http", "https", "ssl"]):
            return "网络::HTTP"
        return "网络"

    # Operating System
    if any(kw in text for kw in ["操作系统", "linux", "内存管理", "进程", "调度",
                                  "文件系统", "io模型", "select", "epoll",
                                  "用户态", "内核态", "虚拟内存"]):
        return "操作系统"

    # Database
    if any(kw in text for kw in ["数据库", "sqlite", "mysql", "sql", "事务",
                                  "索引", "curd"]):
        return "数据库"

    # Data Structures & Algorithms
    if any(kw in text for kw in ["数据结构", "算法", "排序", "二叉树", "链表",
                                  "数组", "栈", "队列", "堆", "图", "哈希",
                                  "字符串", "递归", "动态规划", "复杂度",
                                  "查找", "冒泡", "快排", "归并"]):
        return "算法与数据结构"

    # Android specific
    if any(kw in text for kw in ["android", "安卓"]):
        if any(kw in text for kw in ["binder", "aidl", "ipc", "跨进程", "进程间"]):
            return "Android::IPC"
        if any(kw in text for kw in ["handler", "looper", "message", "消息"]):
            return "Android::Handler"
        if any(kw in text for kw in ["activity", "fragment", "启动模式", "生命周期"]):
            return "Android::组件"
        if any(kw in text for kw in ["view", "布局", "绘制", "事件", "触控",
                                      "recyclerview", "listview", "webview",
                                      "动画", "自定义view"]):
            return "Android::UI"
        if any(kw in text for kw in ["优化", "性能", "内存泄漏", "anr", "卡顿",
                                      "耗电", "启动优化", "布局优化"]):
            return "Android::性能优化"
        if any(kw in text for kw in ["线程", "thread", "asynctask", "handlerthread",
                                      "intentservice", "协程"]):
            return "Android::异步"
        if any(kw in text for kw in ["service", "广播", "broadcast", "contentprovider",
                                      "manifest"]):
            return "Android::组件"
        if any(kw in text for kw in ["window", "dialog", "toast", "notification",
                                      "bitmap", "图片", "缓存", "存储",
                                      "resources"]):
            return "Android::核心机制"
        if any(kw in text for kw in ["编译", "打包", "签名", "混淆", "加固",
                                      "proguard", "multidex", "apk",
                                      "gradle", "构建", "插件化", "组件化",
                                      "热修复", "module"]):
            return "Android::工程实践"
        # More specific Android domain detection
        if any(kw in text for kw in ["四大组件", "启动过程", "aidl", "ams",
                                      "wms", "pms", "systemserver"]):
            return "Android::系统原理"
        if any(kw in text for kw in ["dalvik", "art", "虚拟机", "内存", "回收"]):
            return "Android::底层"
        return "Android"

    # Android engineering
    if any(kw in text for kw in ["工程", "架构", "mvc", "mvp", "mvvm", "clean",
                                  "组件化", "模块化", "插件化", "热修复",
                                  "gradle", "构建"]):
        return "Android::工程实践"

    # Design patterns
    if any(kw in text for kw in ["设计模式", "mvc", "mvp", "mvvm", "单例",
                                  "工厂", "建造者", "代理", "观察者"]):
        return "设计模式"

    # Kotlin
    if any(kw in text for kw in ["kotlin", "协程", "flow", "sealed", "data class",
                                  "委托", "扩展"]):
        return "Kotlin"

    # Non-technical (avoid "面试" as it appears in all interview PDF chapter names)
    if any(kw in text for kw in ["非技术", "hr", "软技能", "职业"]):
        return "综合"

    return "其他"


# =============================================================
# Text Cleaning
# =============================================================

def clean_extracted_text(text: str) -> str:
    """Clean up extracted Markdown text from pymupdf4llm/PyMuPDF."""
    # Remove page numbers and headers (lines with only numbers)
    text = re.sub(r'\n\d+\n', '\n', text)
    # Remove reference links like [text](url)
    text = re.sub(r'\[([^\]]+)\]\(https?://[^\)]+\)', r'\1', text)
    # Remove bold/italic markers **text**
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
    # Remove italic markers *text*
    text = re.sub(r'(?<!\w)\*(?!\*)(.*?)(?<!\*)\*(?!\w)', r'\1', text)
    # Normalize whitespace
    text = re.sub(r' {2,}', ' ', text)
    # Normalize multiple newlines
    text = re.sub(r'\n{3,}', '\n\n', text)
    # Remove leading/trailing whitespace per line
    text = '\n'.join(line.strip() for line in text.split('\n'))
    # Remove bullet markers that got garbled
    text = text.replace('', '•')
    # Remove leading/trailing pipes and special chars
    text = re.sub(r'^[|>\s]+', '', text, flags=re.MULTILINE)
    return text.strip()


def clean_card_content(text: str) -> str:
    """Clean card content (front/back) for better display in Anki."""
    # Remove markdown table rows (lines with mostly pipes)
    text = re.sub(r'^[|\-:\s]+$', '', text, flags=re.MULTILINE)
    # Simplify table pipes in content: "| A | B | C |" -> "A: B, C"
    text = re.sub(r'\|\s*([^|]+)\s*\|\s*([^|]+)\s*\|', r'\1: \2', text)
    # Remove standalone pipes
    text = text.replace('|', '')
    # Escape angle brackets that aren't valid HTML tags (e.g., <K,V>, <JAVA_HOME>)
    # Generic type patterns: <K,V> <Object,Object> <Integer,Object>
    text = re.sub(r'<([A-Za-z0-9_,\s]+)>', r'&lt;\1&gt;', text)
    # UPPERCASE identifiers in angle brackets like <JAVA_HOME>
    text = re.sub(r'<([A-Z][A-Z_0-9]+)>', r'&lt;\1&gt;', text)
    # Escape PHP/XML processing instruction markers <? and <? (but not valid HTML)
    text = text.replace('<?', '&lt;?')
    # Escape <= (less-than-or-equal) that genanki misinterprets as HTML tag start
    text = text.replace('<=', '&lt;=')
    # Collapse multiple spaces
    text = re.sub(r' {2,}', ' ', text)
    # Clean leading/trailing whitespace per line
    text = '\n'.join(line.strip() for line in text.split('\n'))
    return text.strip()


def extract_markdown(filepath: Path) -> str:
    """Extract PDF as Markdown using pymupdf4llm."""
    import pymupdf4llm
    md_text = pymupdf4llm.to_markdown(str(filepath))
    return clean_extracted_text(md_text)


def is_toc_content(text: str) -> bool:
    """Detect if content looks like a Table of Contents / directory page.

    TOC pages typically have many short lines with page numbers,
    or numbered topic entries without substantial technical content.
    """
    lines = text.strip().split('\n')
    if len(lines) < 3:
        return False

    # Count lines that look like TOC entries: start with number or have trailing page numbers
    toc_line_count = 0
    detail_line_count = 0
    for line in lines:
        line = line.strip()
        if not line:
            continue
        # Line is a TOC entry if: starts with number or ends with page number
        is_toc = bool(re.match(r'^\d+[、.．\s]', line))
        # Lines containing only numbers and dots (page numbers)
        is_page_num = bool(re.match(r'^[\d\s.\-—|]+$', line))
        # Short lines with page-like endings "... 33"
        has_page_ref = bool(re.search(r'[\.\s]+\d+\s*$', line))
        if is_toc or is_page_num or has_page_ref:
            toc_line_count += 1
        else:
            detail_line_count += 1

    total_meaningful = toc_line_count + detail_line_count
    if total_meaningful == 0:
        return False

    # If more than 40% of lines are TOC-like, and there are few detail lines, it's a TOC
    toc_ratio = toc_line_count / total_meaningful
    return toc_ratio > 0.4 or (toc_line_count > 5 and detail_line_count < toc_line_count)


# =============================================================
# Step 1: Interview PDF Parser (Regex-based)
# =============================================================

class InterviewPDFParser:
    """Parse the interview PDF which already has Q&A format."""

    def __init__(self, filepath: Path):
        self.filepath = filepath
        self.cards: List[Flashcard] = []

    def parse(self) -> List[Flashcard]:
        """Parse the interview PDF and extract Q&A pairs."""
        log.info(f"Parsing interview PDF: {self.filepath.name}")

        # Step 1: Extract entire document as Markdown
        md_text = self._extract_markdown()

        # Step 2: Parse structured Q&A
        self.cards = self._parse_qa_pairs(md_text)

        log.info(f"Extracted {len(self.cards)} Q&A pairs from interview PDF")
        return self.cards

    def _extract_markdown(self) -> str:
        """Extract full document as Markdown using pymupdf4llm."""
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
        question_count = 0

        # Patterns for hierarchy
        # Match both plain "第一章xxx" and markdown "## 第一章xxx"
        chapter_pattern = re.compile(r'^#{0,4}\s*第[一二三四五六七八九十]+章\s*(.+)$')
        section_pattern = re.compile(r'^#{0,4}\s*第[一二三四五六七八九十]+节[、.．]\s*(.+)$')
        # Subsection like "一、面向对象" or "一、面向对象（⭐⭐⭐）"
        subsection_pattern = re.compile(r'^#{0,4}\s*[一二三四五六七八九十]+[、.．]\s*(.+?)(?:（.*?）)?$')
        # Question pattern: "1、xxx" or "2. xxx" or "3、xxx？"
        question_pattern = re.compile(r'^(\d+)[、.．]\s*(.+)$')

        for line in lines:
            line = line.strip()
            if not line:
                if in_answer and current_answer:
                    current_answer += '\n'
                continue

            # Check for chapter header
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

            # Check for section header
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

            # Check for subsection header (like "一、面向对象")
            m = subsection_pattern.match(line)
            if m and len(line) < 30:  # Must be short to be a header
                # Only treat as subsection if it looks like a topic header
                subsection_text = m.group(1).strip()
                # Don't match if this is just a short answer line
                if not in_answer or (in_answer and len(current_answer) > 200):
                    if in_answer and current_question:
                        self._save_card(cards, current_chapter, current_section, current_subsection,
                                        current_question, current_answer)
                        current_question = ""
                        current_answer = ""
                        in_answer = False
                    current_subsection = self._clean_header(subsection_text)
                    continue

            # Check for question
            m = question_pattern.match(line)
            if m:
                q_text = m.group(2).strip()
                # Heuristic: skip numbered answer list items (very short, no question intent)
                is_list_item = (
                    in_answer and
                    len(q_text) < 30 and  # Very short text
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
                    question_count += 1
                else:
                    # This is a list item in the answer, append it
                    if current_answer:
                        current_answer += '\n' + line
                    else:
                        current_answer = line
                continue

            # If we're in answer mode, accumulate answer text
            if in_answer:
                # Check if this line is likely a continuation of the answer
                # or a new unrelated section
                if current_answer:
                    current_answer += ' ' + line
                else:
                    current_answer = line

        # Save the last question-answer pair
        if in_answer and current_question:
            self._save_card(cards, current_chapter, current_section, current_subsection,
                            current_question, current_answer)

        return cards

    def _clean_header(self, name: str) -> str:
        """Clean a chapter/section header by removing TOC artifacts (dots, page numbers)."""
        # Remove trailing dots and page numbers like "....... 33"
        name = re.sub(r'[\.\s]*\d+\s*$', '', name)
        # Remove any remaining trailing dots
        name = re.sub(r'[\.\s]+$', '', name)
        return name.strip()

    def _save_card(self, cards: List[Flashcard], chapter: str, section: str,
                   subsection: str, question: str, answer: str):
        """Create a flashcard from a parsed Q&A pair and add to list."""
        # Clean headers
        chapter = self._clean_header(chapter)
        section = self._clean_header(section)
        subsection = self._clean_header(subsection)

        # Clean the answer
        answer = answer.strip()
        if not answer or len(answer) < 5:
            return

        # Determine deck hierarchy
        domain = extract_tech_domain(chapter=chapter, section=section, subsection=subsection)
        deck_name = f"Android面试::{domain}" if domain else "Android面试"

        # Build source section chain
        section_parts = [p for p in [chapter, section, subsection] if p]
        source_section = " > ".join(section_parts) if section_parts else "未知章节"

        # Build tags
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


# =============================================================
# Step 2: Knowledge PDF Parser (Heading-based + AI)
# =============================================================

class KnowledgePDFParser:
    """Parse the knowledge reference PDF using heading-based splitting."""

    def __init__(self, filepath: Path):
        self.filepath = filepath
        self.cards: List[Flashcard] = []

    def parse(self) -> List[Flashcard]:
        """Parse the knowledge PDF and generate Q&A cards."""
        log.info(f"Parsing knowledge PDF: {self.filepath.name}")

        # Step 1: Extract as Markdown with page chunks
        md_chunks = self._extract_markdown()

        # Step 2: Split into sections by heading
        sections = self._split_by_headings(md_chunks)
        log.info(f"Split into {len(sections)} sections")

        # Step 3: Generate cards from each section
        for i, section in enumerate(sections):
            cards = self._process_section(section)
            self.cards.extend(cards)

        log.info(f"Generated {len(self.cards)} cards from knowledge PDF")
        return self.cards

    def _extract_markdown(self) -> str:
        """Extract full document as Markdown."""
        return extract_markdown(self.filepath)

    def _clean_section_title(self, title: str) -> str:
        """Clean a section title by removing markdown artifacts."""
        # Remove bold/italic markers
        title = re.sub(r'\*\*(.*?)\*\*', r'\1', title)
        title = title.replace('*', '')
        # Remove extra heading markers
        title = re.sub(r'^#+\s*', '', title)
        # Remove leading punctuation artifacts like "、 、"
        title = re.sub(r'^[、，,.\s]+', '', title)
        # Clean up Chinese punctuation sequences
        title = re.sub(r'[、，,]{2,}', '', title)
        return title.strip()

    def _split_by_headings(self, md_text: str) -> List[Dict[str, Any]]:
        """Split document into sections by Markdown headings."""
        sections = []

        # Try using the TOC from the PDF
        try:
            import fitz
            doc = fitz.open(str(self.filepath))
            toc = doc.get_toc()
            doc.close()
        except Exception as e:
            log.warning(f"Could not read PDF TOC: {e}")
            toc = []

        if toc:
            # Use TOC-based splitting
            lines = md_text.split('\n')
            current_section: Dict[str, Any] = {"title": "前言", "content": "", "level": 0, "breadcrumb": []}

            heading_pattern = re.compile(r'^(#{1,4})\s+(.+)$')

            for line in lines:
                m = heading_pattern.match(line)
                if m:
                    level = len(m.group(1))
                    title = self._clean_section_title(m.group(2).strip())

                    # Save previous section if it has content
                    if current_section["content"].strip():
                        section_copy = current_section.copy()
                        section_copy["content"] = section_copy["content"].strip()
                        sections.append(section_copy)

                    # Update breadcrumb
                    breadcrumb = current_section["breadcrumb"][:]
                    if level <= current_section["level"]:
                        # Going up or same level
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

            # Save last section
            if current_section and current_section["content"].strip():
                sections.append(current_section)
        else:
            # Fallback: split by any heading
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

        # Filter out very small sections (likely page headers/footers)
        sections = [s for s in sections if len(s["content"]) > 100]

        # Filter out TOC/directory sections
        before = len(sections)
        sections = [s for s in sections if not is_toc_content(s["content"])]
        if len(sections) < before:
            log.debug(f"Filtered out {before - len(sections)} TOC/directory sections")

        return sections

    def _process_section(self, section: Dict) -> List[Flashcard]:
        """Process a single section and generate flashcards."""
        cards = []
        title = section["title"]
        content = section["content"]
        breadcrumb = section.get("breadcrumb", [title])

        # Try AI generation first if API key available
        if CONFIG.api_key:
            try:
                ai_cards = self._generate_with_claude(title, content, breadcrumb)
                if ai_cards:
                    return ai_cards
            except Exception as e:
                log.warning(f"AI generation failed for section '{title}': {e}")
                log.warning("Falling back to content-based extraction")

        # Fallback: extract key sentences from content
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

        # Parse JSON response
        try:
            # Try to find JSON block in response
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
        """Fallback: extract key information as basic cards.

        Uses multiple strategies with quality checks to produce useful flashcards
        when AI generation is not available.
        """
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

        # Skip known non-content titles, and strip section numbers from title
        skip_titles = {"目录", "前言", "附录", "参考文献", "索引"}
        clean_title = re.sub(r'^[\d\s.．、\-]+', '', title).strip()
        if not clean_title:
            clean_title = title.strip()
        if clean_title in skip_titles:
            return []

        # Use cleaned title (without section numbers) for card creation
        title = clean_title

        # Clean content: remove markdown artifacts, normalize whitespace
        clean_content = content
        # Remove markdown heading markers
        clean_content = re.sub(r'^#{1,4}\s+', '', clean_content, flags=re.MULTILINE)
        # Remove HTML tags
        clean_content = re.sub(r'<[^>]+>', '', clean_content)
        # Remove markdown links
        clean_content = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', clean_content)
        # Normalize whitespace
        clean_content = re.sub(r'\s+', ' ', clean_content)
        clean_content = clean_content.strip()
        if len(clean_content) < 20:
            return []

        # Split into sentences
        sentences = re.split(r'(?<=[。！？.!?])\s*', clean_content)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 15]

        # Strategy 1: Use definition/explanation sentences as Q&A cards
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

                        # Strip numeric prefixes like "3 " or "1.1 " from the term
                        term = re.sub(r'^[\d\s.．、]+', '', raw_term).strip()
                        if not term:
                            term = raw_term  # Keep original if stripping removed everything

                        # Only use well-formed definitions
                        if (5 < len(term) < 60 and len(defn) > 10
                                and not term.isdigit()
                                and not term.startswith('第')):  # Skip "第一章" type terms
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

        # Strategy 2: Use substantive sentences as standalone knowledge cards
        # Only if we don't already have enough cards
        if len(cards) < 2:
            existing_backs = {c.back[:50] for c in cards}
            for sent in sentences:
                sent = sent.strip()
                # Quality filters
                if len(sent) < 30 or len(sent) > 500:
                    continue
                # Skip sentences that are just page numbers or navigation
                if re.match(r'^[\d\s/\-—|\\]+$', sent):
                    continue
                # Skip if very similar to an existing card's answer
                if sent[:50] in existing_backs:
                    continue
                # Must contain technical Chinese content (not just numbers/symbols)
                chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', sent))
                if chinese_chars < 10:
                    continue

                # Create a card with a meaningful question from sentence content
                # Try to extract a key term from the beginning of the sentence
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
                    # First substantive card: use title + key info as question
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


# =============================================================
# Step 3: TXT File Parser
# =============================================================

class TxtParser:
    """Parse TXT files and generate Q&A cards with AI."""

    def __init__(self, filepath: Path):
        self.filepath = filepath
        self.cards: List[Flashcard] = []

    def parse(self) -> List[Flashcard]:
        """Parse a text file and generate cards."""
        log.info(f"Parsing TXT file: {self.filepath.name}")

        # Step 1: Read the file with proper encoding
        questions = self._read_questions()
        log.info(f"Read {len(questions)} questions from {self.filepath.name}")

        # Step 2: Generate cards
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

        # Pattern for category headers (like "java基础篇：" or "android基础篇：")
        category_pattern = re.compile(r'^([\u4e00-\u9fff\w]+)[：:]')

        # Pattern for numbered questions (like "1、xxx" or "2. xxx")
        question_pattern = re.compile(r'^\s*(\d+)[、.．]\s*(.*)')

        # Pattern for sub-items (like "   1、小文件上传")
        sub_item_pattern = re.compile(r'^\s+(\d+)[、.．]\s+(.*)')

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Check for category header
            m = category_pattern.match(line)
            if m and len(line) < 30:
                current_category = m.group(1)
                continue

            # Check for sub-item (belongs to parent question, skip as separate card)
            m = sub_item_pattern.match(line)
            if m:
                # Skip sub-items, they're details of the main question
                continue

            # Check for numbered question
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

            # Non-numbered question line
            if len(line) > 5 and not line.startswith('(') and not line.startswith('（'):
                if current_question:
                    current_question += " " + line
                else:
                    current_question = line

        # Handle the last pending question
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

        # Try different encodings
        for enc in ['utf-8', 'gbk', 'gb2312', 'gb18030']:
            try:
                return raw.decode(enc)
            except UnicodeDecodeError:
                continue

        # Fallback: use gbk with error handling
        return raw.decode('gbk', errors='replace')

    def _process_question(self, q_data: Dict) -> List[Flashcard]:
        """Process a single question and generate cards."""
        q_text = q_data["text"]
        category = q_data.get("category", "")

        # Try AI generation first
        if CONFIG.api_key:
            try:
                ai_cards = self._generate_with_claude(q_text, category)
                if ai_cards:
                    return ai_cards
            except Exception as e:
                log.warning(f"AI generation failed for question '{q_text[:30]}...': {e}")

        # Fallback: create a card with just the question
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


# =============================================================
# Step 4: Deduplication
# =============================================================

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
                    # Merge: keep the better answer, merge sources
                    is_dup = True

                    # Merge tags
                    existing.tags = list(set(existing.tags + card.tags))

                    # Merge source info
                    existing.source_section += f" | also in: {card.source_section}"

                    # Keep longer answer
                    if len(card.back) > len(existing.back):
                        existing.back = card.back

                    log.debug(f"Duplicate found: '{card.front[:30]}...' matches '{existing.front[:30]}...'")
                    break

            if not is_dup:
                unique_cards.append(card)

        duplicates_removed = len(cards) - len(unique_cards)
        log.info(f"Removed {duplicates_removed} duplicates, {len(unique_cards)} unique cards remain")

        return unique_cards


# =============================================================
# Step 5: Quality Filter
# =============================================================

class QualityFilter:
    """Filter and validate flashcards."""

    @staticmethod
    def validate(cards: List[Flashcard]) -> List[Flashcard]:
        """Remove invalid or low-quality cards."""
        valid = []

        for card in cards:
            # Check front is not empty
            if not card.front or len(card.front.strip()) < 5:
                continue

            # Check back is not empty
            if not card.back or len(card.back.strip()) < 5:
                continue

            # Check front is not a pure number
            if card.front.strip().isdigit():
                continue

            # Check for gibberish (too many special chars)
            special_ratio = sum(1 for c in card.front if c in '*#$%^&') / max(len(card.front), 1)
            if special_ratio > 0.3:
                continue

            # Reject placeholder cards only when answer is truly minimal
            # (Keep TXT file question prompts as they have value even without AI answers)
            if card.back == "【待补充答案】":
                continue

            # Reject cards with garbled questions:
            # 1. Question starts with a bare number + space (like "3 方法")
            if re.match(r'^(什么是)?\d+\s+\S', card.front) and len(card.front) < 30:
                continue
            # 2. Question has garbled fragments from poor parsing (trailing punctuation artifacts)
            if re.search(r'(?:被？|为？)$', card.front):
                continue
            # 3. Question is very short (under 5 chars after stripping whitespace)
            if len(card.front.strip()) < 5:
                continue
            # 4. Question is too short (under 5 chars) after stripping
            if len(card.front.replace('？', '').replace('?', '').strip()) < 5:
                continue
            # 5. Question that is just "什么是这个过程？" or "什么是这个？" (too vague)
            if re.search(r'^什么是[这那]个', card.front):
                continue
            # 6. Question ends with garbled trailing fragment (e.g., "不能？" at end of question)
            if re.search(r'[是就有]？$', card.front):
                continue

            # Check that content has non-trivial Chinese or technical content
            chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', card.front))
            if chinese_chars < 2 and len(card.front) > 10:
                continue

            valid.append(card)

        removed = len(cards) - len(valid)
        if removed:
            log.info(f"Quality filter removed {removed} invalid cards")

        return valid


# =============================================================
# Step 6: Anki Exporter
# =============================================================

class AnkiExporter:
    """Export flashcards to Anki .apkg format using genanki."""

    def __init__(self):
        self.models = self._create_models()
        self.decks: Dict[str, Any] = {}

    def _create_models(self) -> Dict:
        """Create genanki models for basic and cloze card types."""
        # Basic Q&A model
        basic_model = genanki.Model(
            CONFIG.basic_model_id,
            'Android 面试 Q&A',
            fields=[
                {'name': 'Question'},
                {'name': 'Answer'},
                {'name': 'Source'},
                {'name': 'Section'},
            ],
            templates=[{
                'name': 'Card 1',
                'qfmt': '''
                    <div class="card-front">
                        <div class="question">{{Question}}</div>
                        <div class="source-tag">{{Source}}</div>
                    </div>
                ''',
                'afmt': '''
                    <div class="card-back">
                        <div class="question">{{Question}}</div>
                        <hr id="answer">
                        <div class="answer">{{Answer}}</div>
                        <hr>
                        <div class="source-info">
                            <small>来源: {{Source}} | {{Section}}</small>
                        </div>
                    </div>
                ''',
            }],
            css='''
                .card {
                    font-family: "PingFang SC", "Noto Sans SC", "Helvetica Neue", sans-serif;
                    font-size: 16px;
                    line-height: 1.8;
                    color: #333;
                    padding: 20px;
                }
                .card.night_mode {
                    color: #e0e0e0;
                }
                .card-front {
                    text-align: left;
                }
                .card-back {
                    text-align: left;
                }
                .question {
                    font-size: 18px;
                    font-weight: 600;
                    color: #1a1a2e;
                    margin-bottom: 10px;
                }
                .night_mode .question {
                    color: #a8d8ea;
                }
                .answer {
                    font-size: 16px;
                    color: #333;
                    line-height: 1.8;
                }
                .night_mode .answer {
                    color: #e0e0e0;
                }
                .source-tag {
                    font-size: 11px;
                    color: #999;
                    margin-top: 5px;
                }
                .source-info {
                    font-size: 11px;
                    color: #aaa;
                    margin-top: 10px;
                    padding-top: 10px;
                    border-top: 1px solid #eee;
                }
                .night_mode .source-info {
                    border-top-color: #444;
                    color: #777;
                }
            '''
        )

        # Cloze model
        cloze_model = genanki.Model(
            CONFIG.cloze_model_id,
            'Android 面试 Cloze',
            model_type=genanki.Model.CLOZE,
            fields=[
                {'name': 'Text'},
                {'name': 'Extra'},
                {'name': 'Source'},
                {'name': 'Section'},
            ],
            templates=[{
                'name': 'Cloze Card',
                'qfmt': '{{cloze:Text}}',
                'afmt': '''
                    {{cloze:Text}}
                    <hr id="answer">
                    {{Extra}}
                    <hr>
                    <div class="source-info">
                        <small>来源: {{Source}} | {{Section}}</small>
                    </div>
                ''',
            }],
            css='''
                .card {
                    font-family: "PingFang SC", "Noto Sans SC", "Helvetica Neue", sans-serif;
                    font-size: 16px;
                    line-height: 1.8;
                    color: #333;
                    padding: 20px;
                }
                .cloze {
                    font-weight: bold;
                    color: #e74c3c;
                }
                .night_mode .cloze {
                    color: #ff6b6b;
                }
                .source-info {
                    font-size: 11px;
                    color: #aaa;
                    margin-top: 10px;
                    padding-top: 10px;
                    border-top: 1px solid #eee;
                }
            '''
        )

        return {
            "basic": basic_model,
            "cloze": cloze_model,
        }

    def _get_deck(self, deck_name: str) -> Any:
        """Get or create a genanki deck by name."""
        if deck_name not in self.decks:
            # Create a stable deck ID from the name
            deck_id = CONFIG.parent_deck_id + abs(hash(deck_name)) % (1 << 20)
            self.decks[deck_name] = genanki.Deck(deck_id, deck_name)
        return self.decks[deck_name]

    def export(self, cards: List[Flashcard], output_path: Path) -> str:
        """Export cards to .apkg file."""
        log.info(f"Exporting {len(cards)} cards to {output_path}")

        for card in cards:
            deck = self._get_deck(card.deck_name)

            if card.card_type == "cloze":
                note = genanki.Note(
                    model=self.models["cloze"],
                    fields=[card.front, card.back, card.source_file, card.source_section],
                    tags=card.tags,
                )
            else:
                note = genanki.Note(
                    model=self.models["basic"],
                    fields=[card.front, card.back, card.source_file, card.source_section],
                    tags=card.tags,
                )

            deck.add_note(note)

        # Create package with all decks
        deck_list = list(self.decks.values())
        package = genanki.Package(deck_list)

        # Write to file
        output_path.parent.mkdir(parents=True, exist_ok=True)
        package.write_to_file(str(output_path))

        log.info(f"Successfully exported to {output_path}")
        log.info(f"Total decks: {len(self.decks)}")
        for name, d in sorted(self.decks.items()):
            log.info(f"  Deck: {name} ({len(d.notes)} notes)")

        return str(output_path)


# =============================================================
# Main Pipeline
# =============================================================

def discover_source_files(data_dir: Path) -> List[Path]:
    """Discover all PDF and TXT files in the data directory."""
    files: List[Path] = []
    for ext in ["*.pdf", "*.txt"]:
        files.extend(data_dir.glob(ext))

    # Sort by name for consistent order
    files.sort(key=lambda p: p.name)

    return files


def process_file(filepath: Path) -> List[Flashcard]:
    """Process a single source file and return flashcards."""
    ext = filepath.suffix.lower()

    if ext == ".pdf":
        name_lower = filepath.stem.lower()
        if "面试" in name_lower or "阿里巴巴" in name_lower:
            parser: Any = InterviewPDFParser(filepath)
        else:
            parser = KnowledgePDFParser(filepath)
    elif ext == ".txt":
        parser = TxtParser(filepath)
    else:
        log.warning(f"Unsupported file type: {filepath}")
        return []

    try:
        return parser.parse()
    except Exception as e:
        log.error(f"Error processing {filepath}: {e}")
        import traceback
        log.error(traceback.format_exc())
        return []


def generate_summary_report(cards: List[Flashcard], output_path: Path):
    """Generate a summary report of the cards."""
    lines = []
    lines.append("=" * 60)
    lines.append("Anki 卡片生成报告")
    lines.append("=" * 60)
    lines.append(f"生成时间: 2026-06-08")
    lines.append(f"总卡片数: {len(cards)}")
    lines.append(f"输出文件: {output_path}")
    lines.append("")

    # Count by source
    sources: Dict[str, int] = {}
    for card in cards:
        sources[card.source_file] = sources.get(card.source_file, 0) + 1

    lines.append("--- 按来源统计 ---")
    for src, count in sorted(sources.items()):
        lines.append(f"  {src}: {count} 张卡片")

    # Count by deck
    decks: Dict[str, int] = {}
    for card in cards:
        decks[card.deck_name] = decks.get(card.deck_name, 0) + 1

    lines.append("\n--- 按牌组统计 ---")
    for deck, count in sorted(decks.items()):
        lines.append(f"  {deck}: {count} 张卡片")

    # Sample cards
    lines.append("\n--- 抽样卡片 (前10张) ---")
    for i, card in enumerate(cards[:10]):
        lines.append(f"\n卡片 {i+1}:")
        lines.append(f"  牌组: {card.deck_name}")
        lines.append(f"  问题: {card.front[:80]}...")
        lines.append(f"  答案: {card.back[:80]}...")
        lines.append(f"  标签: {', '.join(card.tags)}")
        lines.append(f"  来源: {card.source_file} > {card.source_section}")

    lines.append("\n" + "=" * 60)

    report = '\n'.join(lines)

    # Write report
    report_path = output_path.with_suffix('.txt')
    report_path.write_text(report, encoding='utf-8')
    log.info(f"Report written to {report_path}")

    # Also print summary
    print()
    print(report)


def check_api_key():
    """Check and report API key status."""
    if CONFIG.api_key:
        log.info(f"Anthropic API key found ({CONFIG.api_key[:8]}...{CONFIG.api_key[-4:]})")
        log.info(f"AI generation will be used for knowledge PDF and TXT files.")
        return True
    else:
        log.warning("No ANTHROPIC_API_KEY found in environment.")
        log.warning("AI generation will be skipped for knowledge PDF and TXT files.")
        log.warning("Only the interview PDF will be fully processed.")
        log.warning("To enable AI generation, set: export ANTHROPIC_API_KEY='your-key-here'")
        return False


def main():
    """Main pipeline entry point."""
    log.info("=" * 50)
    log.info("PDF-to-Anki Card Builder Pipeline")
    log.info("=" * 50)

    # Check API key
    check_api_key()
    print()

    # Discover source files
    data_dir = CONFIG.data_dir.resolve()
    if not data_dir.exists():
        log.error(f"Data directory not found: {data_dir}")
        sys.exit(1)

    source_files = discover_source_files(data_dir)
    if not source_files:
        log.error(f"No PDF or TXT files found in {data_dir}")
        sys.exit(1)

    log.info(f"Found {len(source_files)} source files:")
    for f in source_files:
        log.info(f"  - {f.name} ({f.stat().st_size / 1024:.0f} KB)")
    print()

    # Phase 1: Extract and parse all source files
    log.info("Phase 1: Extraction and Parsing")
    log.info("-" * 40)
    all_cards: List[Flashcard] = []
    source_stats: Dict[str, int] = {}

    for filepath in source_files:
        cards = process_file(filepath)
        all_cards.extend(cards)
        source_stats[filepath.name] = len(cards)
        log.info(f"  -> {filepath.name}: {len(cards)} cards")

    print()

    # Check minimum card requirements for PDFs
    log.info("Phase 2: Quality Check")
    log.info("-" * 40)

    pdf_files = [f for f in source_files if f.suffix.lower() == '.pdf']
    for pdf in pdf_files:
        count = source_stats.get(pdf.name, 0)
        if count < CONFIG.min_cards_per_pdf:
            log.warning(f"  {pdf.name}: only {count} cards (minimum: {CONFIG.min_cards_per_pdf})")
        else:
            log.info(f"  {pdf.name}: {count} cards (meets minimum)")

    # Phase 2: Quality filter
    filtered_cards = QualityFilter.validate(all_cards)
    log.info(f"  Quality filter: {len(all_cards)} -> {len(filtered_cards)} cards")

    # Phase 3: Deduplication
    log.info(f"\nPhase 3: Deduplication")
    log.info("-" * 40)
    deduper = Deduplicator(threshold=CONFIG.dedup_threshold)
    unique_cards = deduper.deduplicate(filtered_cards)

    print()

    # Phase 4: Export to .apkg
    log.info("Phase 4: Anki Export")
    log.info("-" * 40)
    output_dir = CONFIG.output_dir.resolve()
    output_path = output_dir / CONFIG.output_file

    exporter = AnkiExporter()
    result_path = exporter.export(unique_cards, output_path)

    print()

    # Generate summary report
    generate_summary_report(unique_cards, output_path)

    log.info("Pipeline completed successfully!")
    log.info(f"Output: {result_path}")
    log.info(f"Total cards: {len(unique_cards)}")

    return result_path


if __name__ == "__main__":
    main()
