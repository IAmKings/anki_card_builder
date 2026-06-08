"""直接用已验证的正则提取 Kotlin 协程 Q&A 并生成卡片 JSON"""
import re
import json

def parse_md(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        text = f.read()

    cards = []
    # Track current section
    section = "综合"

    # Split at H3 headings: ### **N\. ...
    blocks = re.split(r'\n(?=### \*\*\d+\\\. )', text)

    for block in blocks:
        # Track section changes
        sec = re.search(r'## \*\*(.+?)\*\*', block)
        if sec:
            s = sec.group(1)
            if '基础' in s or '设计' in s: section = "基础与设计哲学"
            elif '上下文' in s or '调度' in s: section = "上下文与调度器"
            elif '生命周期' in s or '取消' in s: section = "生命周期与取消"
            elif '异常' in s or '并发安全' in s: section = "异常处理与并发安全"
            elif 'Channel' in s: section = "Channel管道"
            elif 'Flow 全家桶' in s or '核心原理' in s: section = "Flow核心原理"
            elif '状态流' in s or 'StateFlow' in s or 'SharedFlow' in s: section = "SharedFlow与StateFlow"
            elif '背压' in s or 'Backpressure' in s: section = "背压处理"
            elif 'Android' in s or '实战' in s or 'Jetpack' in s: section = "Android实战"
            elif '测试' in s: section = "测试与调试"
            elif '源码' in s: section = "源码分析"

        # Extract question
        qm = re.match(r'### \*\*\d+\\\.\s*(.+?)\*\*', block)
        if not qm:
            continue
        question = qm.group(1).strip()

        # Extract answer
        am = re.search(r'\*\*确切答案[：:]\*\*\s*(.+?)(?=\n(?:### \*\*|\n## \*\*|\n\*\*提示|\Z))', block, re.DOTALL)
        if not am:
            continue
        answer = am.group(1).strip()

        # Clean answer
        answer = re.sub(r'^\\?\*\s*', '', answer)  # strip leading bullet
        answer = re.sub(r'\n{3,}', '\n\n', answer)   # compress blank lines
        answer = re.sub(r'  +', ' ', answer)          # compress spaces
        # Convert **bold** to <b>bold</b>
        answer = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', answer)
        # Clean escaped asterisks
        answer = answer.replace('\\*', '')
        answer = answer.replace('\\-', '-')
        answer = answer.replace('\\>', '>')
        # Limit length for Anki readability
        if len(answer) > 2000:
            answer = answer[:2000] + '...'

        cards.append({
            "front": question,
            "back": answer,
            "card_type": "basic",
            "tags": ["Kotlin", "协程", section],
            "source": f"Kotlin 协程深入的 100 道题 > {section}"
        })

    return cards


# Parse both files
all_cards = []
for f in [
    "data/Kotlin 协程深入的 100 道题(1-40).md",
    "data/Kotlin 协程深入的 100 道题(41-100).md"
]:
    cards = parse_md(f)
    print(f"{f}: {len(cards)} 张")
    all_cards.extend(cards)

print(f"\n总计: {len(all_cards)} 张")

# Save
with open("output/kotlin_coroutine_cards.json", "w", encoding="utf-8") as f:
    json.dump(all_cards, f, ensure_ascii=False, indent=2)

print("已保存: output/kotlin_coroutine_cards.json")
