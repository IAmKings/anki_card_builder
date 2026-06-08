"""
知识笔记PDF AI处理器
使用Claude API逐章节生成高质量Anki卡片
"""
import os
import re
import json
import time
import fitz
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional

# ============================================================
# Configuration
# ============================================================

@dataclass
class Config:
    pdf_path: str = "data/Android 核心知识点笔记.pdf"
    output_path: str = "output/knowledge_cards.json"
    model: str = "claude-sonnet-4-6"  # 或 claude-haiku-4-5 省钱
    max_tokens: int = 4096
    min_section_pages: int = 2  # 至少2页的章节才用AI处理

config = Config()

# ============================================================
# Prompt template - Wozniak原则
# ============================================================

SYSTEM_PROMPT = """你是Android面试题出题专家。请根据提供的知识点文本，生成高质量的Anki闪卡。

## 出题原则（Wozniak's Rules）：
1. 原子性：每张卡片只测试一个知识点
2. 清晰性：问题必须只有一个明确答案
3. 简洁性：使用简单直接的语言
4. 避免枚举：将列表拆分为独立卡片
5. 不要出"是/否"类问题

## 卡片类型选择：
- 基础问答(90%)：适合概念解释、原理说明
- Cloze填空(10%)：适合关键数值、特定术语

## 输出格式（严格JSON）：
```json
{
  "cards": [
    {
      "front": "问题内容？",
      "back": "答案内容",
      "type": "basic",
      "tags": ["Java", "JVM"]
    },
    {
      "front": "{{c1::G1收集器}}采用{{c2::标记-整理}}算法，不会产生内存碎片",
      "back": "",
      "type": "cloze",
      "tags": ["Java", "JVM", "GC"]
    }
  ]
}
```

## 中文规范：
- front以问号结尾（Cloze除外）
- 专业术语保持英文（如HashMap、CMS、G1）
- 答案准确、完整，可用<br>换行"""

# ============================================================
# Section extraction
# ============================================================

def extract_sections(pdf_path: str) -> List[Dict]:
    """从PDF提取章节文本"""
    doc = fitz.open(pdf_path)
    toc = doc.get_toc()

    sections = []
    for i, (level, title, page) in enumerate(toc):
        if level != 2:
            continue

        # Find end page
        end_page = doc.page_count
        for j in range(i+1, len(toc)):
            if toc[j][0] <= 2:
                end_page = toc[j][2] - 1
                break
        end_page = min(end_page, doc.page_count)

        pages = end_page - page + 1
        if pages < config.min_section_pages:
            continue

        # Extract full text
        text_parts = []
        for p in range(page - 1, end_page):
            page_text = doc[p].get_text()
            # Clean: remove obvious TOC artifacts
            page_text = re.sub(r'\.{4,}\d+', '', page_text)  # TOC dots+page numbers
            text_parts.append(page_text)

        full_text = '\n'.join(text_parts)

        # Detect chapter context
        chapter = "其他"
        if page < 64:
            chapter = "Java"
        elif page < 188:
            chapter = "Android"
        elif page < 246:
            chapter = "Android扩展"
        elif page < 261:
            chapter = "开源库"
        elif page < 281:
            chapter = "设计模式"
        elif page < 282:
            chapter = "Gradle"
        else:
            chapter = "算法"

        sections.append({
            "title": title.strip(),
            "chapter": chapter,
            "pages": pages,
            "text": full_text
        })

    doc.close()
    return sections


# ============================================================
# De-duplication
# ============================================================

def deduplicate_cards(cards: List[Dict], threshold: float = 0.85) -> List[Dict]:
    """基于front文本相似度去重"""
    from difflib import SequenceMatcher

    def normalize(s: str) -> str:
        return re.sub(r'[^\w\u4e00-\u9fff]', '', s).lower()

    unique = []
    for card in cards:
        is_dup = False
        norm_new = normalize(card['front'])
        for existing in unique:
            norm_existing = normalize(existing['front'])
            if SequenceMatcher(None, norm_new, norm_existing).ratio() > threshold:
                # Merge tags
                existing_tags = set(existing.get('tags', []))
                new_tags = set(card.get('tags', []))
                existing['tags'] = list(existing_tags | new_tags)
                is_dup = True
                break
        if not is_dup:
            unique.append(card)

    return unique


# ============================================================
# Quality filter
# ============================================================

def quality_filter(cards: List[Dict]) -> List[Dict]:
    """过滤低质量卡片"""
    valid = []
    for card in cards:
        front = card.get('front', '')
        back = card.get('back', '')
        ctype = card.get('type', 'basic')

        # Cloze: must have {{cN::...}} pattern
        if ctype == 'cloze':
            if not re.search(r'\{\{c\d+::.+?\}\}', front):
                continue
            valid.append(card)
            continue

        # Basic: must have meaningful Q&A
        # Remove Chinese punctuation for counting
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', front))
        if chinese_chars < 5:
            continue

        chinese_back = len(re.findall(r'[\u4e00-\u9fff]', back))
        if chinese_back < 10:
            continue

        # No placeholder patterns
        bad_patterns = ['以下说法正确的是', '简述：', '关于.*以下']
        if any(re.search(p, front) for p in bad_patterns):
            continue

        # Front should ideally end with question mark
        # (not strict, some good cards don't)

        valid.append(card)

    return valid


# ============================================================
# AI API call
# ============================================================

def call_claude_api(section_title: str, chapter: str, text: str) -> List[Dict]:
    """Call Claude API to generate Q&A cards for a section"""
    import anthropic

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print(f"  ⚠️  无API Key，跳过: {section_title}")
        return []

    client = anthropic.Anthropic(api_key=api_key)

    # Truncate text if too long (leave room for response)
    max_input = 8000
    if len(text) > max_input:
        text = text[:max_input] + "\n...(内容已截断)"

    user_prompt = f"""章节: [{chapter}] {section_title}

知识点内容:
{text}

请为以上内容生成Anki闪卡（JSON格式）。重点提取面试常考的核心知识点。"""

    try:
        response = client.messages.create(
            model=config.model,
            max_tokens=config.max_tokens,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}]
        )

        content = response.content[0].text

        # Extract JSON from response
        json_match = re.search(r'```json\s*(.*?)\s*```', content, re.DOTALL)
        if json_match:
            content = json_match.group(1)
        else:
            # Try to find JSON directly
            json_match = re.search(r'\{[\s\S]*"cards"[\s\S]*\}', content)
            if json_match:
                content = json_match.group(0)

        result = json.loads(content)
        cards = result.get('cards', [])

        # Add source info
        for card in cards:
            card['source'] = f"Android 核心知识点笔记.pdf > {section_title}"
            card['tags'] = list(set(card.get('tags', []) + [chapter, section_title.split()[0] if section_title else '']))

        print(f"  ✅ {section_title}: 生成 {len(cards)} 张卡片")
        return cards

    except json.JSONDecodeError as e:
        print(f"  ❌ JSON解析失败 [{section_title}]: {e}")
        print(f"  Raw response: {content[:200]}...")
        return []
    except Exception as e:
        print(f"  ❌ API调用失败 [{section_title}]: {e}")
        return []


# ============================================================
# Main pipeline
# ============================================================

def main():
    print("=" * 60)
    print("知识笔记 AI 卡片生成器")
    print("=" * 60)

    # 1. Extract sections
    print("\n[1/4] 提取PDF章节...")
    sections = extract_sections(config.pdf_path)
    print(f"  提取了 {len(sections)} 个章节 (>= {config.min_section_pages} 页)")

    # 2. Generate cards via AI
    print("\n[2/4] AI生成卡片...")
    all_cards = []
    has_api_key = bool(os.getenv("ANTHROPIC_API_KEY"))

    if not has_api_key:
        print("  ⚠️  ANTHROPIC_API_KEY 未设置！")
        print("  请设置环境变量后重试: export ANTHROPIC_API_KEY='your-key'")
        print("  将跳过AI生成步骤。")
    else:
        for i, section in enumerate(sections):
            print(f"\n  [{i+1}/{len(sections)}] {section['title']} ({section['pages']}p)...")
            cards = call_claude_api(
                section['title'],
                section['chapter'],
                section['text']
            )
            all_cards.extend(cards)
            # Rate limiting
            if cards:
                time.sleep(0.5)

    # 3. Quality filter
    print(f"\n[3/4] 质量过滤 (处理前: {len(all_cards)} 张)...")
    filtered = quality_filter(all_cards)
    print(f"  过滤后: {len(filtered)} 张 (移除 {len(all_cards) - len(filtered)} 张)")

    # 4. Deduplicate
    print(f"\n[4/4] 去重...")
    final_cards = deduplicate_cards(filtered)
    print(f"  去重后: {len(final_cards)} 张 (移除 {len(filtered) - len(final_cards)} 张)")

    # Save
    os.makedirs(os.path.dirname(config.output_path), exist_ok=True)
    with open(config.output_path, 'w', encoding='utf-8') as f:
        json.dump(final_cards, f, ensure_ascii=False, indent=2)

    print(f"\n{'=' * 60}")
    print(f"✅ 完成！卡片已保存到: {config.output_path}")
    print(f"   总卡片数: {len(final_cards)}")
    print(f"{'=' * 60}")

    # Stats by chapter
    chapter_counts = {}
    for card in final_cards:
        ch = card.get('source', '').split(' > ')[0] if ' > ' in card.get('source', '') else '未知'
        chapter_counts[ch] = chapter_counts.get(ch, 0) + 1

    if chapter_counts:
        print("\n按章节统计:")
        for ch, count in sorted(chapter_counts.items(), key=lambda x: -x[1]):
            print(f"  {ch}: {count} 张")


if __name__ == '__main__':
    main()
