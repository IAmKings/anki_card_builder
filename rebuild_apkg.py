"""
合并所有来源卡片 → 去重 → 重建 APKG
独立运行，不依赖 main.py
"""
import json
import re
import os
import hashlib
from difflib import SequenceMatcher
import genanki

# ============================================================
# Config
# ============================================================
MODEL_ID = 1607392319
DECK_ROOT_ID = 2059400110
SIMILARITY_THRESHOLD = 0.85

# ============================================================
# Load knowledge AI cards
# ============================================================
def load_knowledge_cards():
    with open("output/knowledge_ai_cards.json", "r", encoding="utf-8") as f:
        cards = json.load(f)

    result = []
    for c in cards:
        result.append({
            "front": c["front"],
            "back": c["back"],
            "card_type": c.get("type", "basic"),
            "tags": c.get("tags", []),
            "source": f"Android 核心知识点笔记.pdf > {c.get('source', 'AI Generated')}"
        })
    return result

# ============================================================
# Load interview PDF cards (simple re-extract)
# ============================================================
def load_interview_cards():
    """从面试题集PDF重新提取（用main.py的解析器）"""
    import sys
    sys.path.insert(0, '.')
    from pathlib import Path
    from main import InterviewPDFParser
    parser = InterviewPDFParser(Path("data/阿里巴巴Android面试题集（答案解析）.pdf"))
    cards = parser.parse()
    result = []
    for c in cards:
        src = getattr(c, 'source_file', '') + ' > ' + getattr(c, 'source_section', '')
        result.append({
            "front": c.front,
            "back": c.back,
            "card_type": getattr(c, 'card_type', 'basic'),
            "tags": c.tags,
            "source": src.strip(' >')
        })
    return result

# ============================================================
# Load txt cards
# ============================================================
def load_txt_cards():
    """从txt文件提取"""
    import sys
    sys.path.insert(0, '.')
    from pathlib import Path
    from main import TxtParser
    result = []
    for f in sorted(os.listdir("data")):
        if f.endswith('.txt'):
            parser = TxtParser(Path(f"data/{f}"))
            cards = parser.parse()
            for c in cards:
                src = getattr(c, 'source_file', '') + ' > ' + getattr(c, 'source_section', '')
                result.append({
                    "front": c.front,
                    "back": c.back,
                    "card_type": getattr(c, 'card_type', 'basic'),
                    "tags": c.tags,
                    "source": src.strip(' >')
                })
    return result

# ============================================================
# Quality filter
# ============================================================
def quality_filter(cards):
    valid = []
    for card in cards:
        front = card.get('front', '')
        back = card.get('back', '')
        ctype = card.get('card_type', 'basic')

        # Cloze: must have {{cN::...}}
        if ctype == 'cloze':
            if not re.search(r'\{\{c\d+::.+?\}\}', front):
                continue
            valid.append(card)
            continue

        # Basic: meaningful Q&A
        chinese_front = len(re.findall(r'[\u4e00-\u9fff]', front))
        if chinese_front < 5:
            continue
        chinese_back = len(re.findall(r'[\u4e00-\u9fff]', back))
        if chinese_back < 10:
            continue

        # No placeholder / garbage patterns
        bad = ['以下说法正确的是', '简述：', '什么是对于', '什么是3 ']
        if any(p in front for p in bad):
            continue

        valid.append(card)
    return valid

# ============================================================
# Deduplication
# ============================================================
def deduplicate(cards, threshold=0.85):
    def normalize(s):
        return re.sub(r'[^\w\u4e00-\u9fff]', '', s).lower()

    unique = []
    for card in cards:
        is_dup = False
        nf = normalize(card['front'])
        for existing in unique:
            ne = normalize(existing['front'])
            if SequenceMatcher(None, nf, ne).ratio() > threshold:
                # Merge tags
                et = set(existing.get('tags', []))
                ct = set(card.get('tags', []))
                existing['tags'] = list(et | ct)
                # Merge sources
                if card['source'] not in existing['source']:
                    existing['source'] += ' | ' + card['source']
                is_dup = True
                break
        if not is_dup:
            unique.append(card)
    return unique

# ============================================================
# Domain detection for deck assignment
# ============================================================
def get_deck_name(card):
    """Assign deck based on tags"""
    tags = [t.lower() for t in card.get('tags', [])]
    tag_str = ' '.join(tags)

    # Java domain
    java_kw = ['java', 'jvm', 'gc', '集合', '并发', '线程', '锁', '反射', '泛型',
               'string', 'hashmap', 'volatile', 'synchronized', '设计模式']
    android_kw = ['android', 'activity', 'fragment', 'service', 'view', 'handler',
                  'ipc', 'binder', 'bitmap', 'context', 'webview', 'jetpack',
                  'livedata', 'viewmodel', 'retrofit', 'glide', 'rxjava',
                  'recyclerview', 'constraintlayout', 'leakcanary', 'eventbus',
                  'okhttp', 'proguard', 'ndk', 'jni', 'art', 'dalvik', 'hook',
                  '加固', '签名', '打包', '启动流程', '屏幕适配', 'anr']
    kotlin_kw = ['kotlin', '协程', 'lateinit', 'lazy', '委托', 'data class']
    network_kw = ['网络', 'http', 'https', 'tcp', 'socket', 'rest']
    algo_kw = ['算法', '排序', '链表', '二叉树', '栈', '队列', '动态规划', '二分',
               '哈希', '贪心', '堆', '矩阵', '字符串处理', 'bfs', 'dfs']
    os_kw = ['操作系统', '进程', '内存']
    db_kw = ['数据库', 'sql', 'sqlite']

    def matches(kw_list):
        return any(k in tag_str for k in kw_list)

    if matches(java_kw) and matches(android_kw):
        return "Android面试::Java"
    elif matches(java_kw):
        return "Android面试::Java"
    elif matches(kotlin_kw):
        return "Android面试::Kotlin"
    elif matches(android_kw):
        return "Android面试::Android"
    elif matches(network_kw):
        return "Android面试::网络"
    elif matches(algo_kw):
        return "Android面试::算法与数据结构"
    elif matches(os_kw):
        return "Android面试::操作系统"
    elif matches(db_kw):
        return "Android面试::数据库"
    else:
        return "Android面试::综合"

# ============================================================
# Build .apkg
# ============================================================
def build_apkg(cards, output_path):
    # Define models
    basic_model = genanki.Model(
        MODEL_ID,
        'Android面试-基础问答',
        fields=[
            {'name': 'Question'},
            {'name': 'Answer'},
            {'name': 'Source'},
        ],
        templates=[{
            'name': 'Basic Card',
            'qfmt': '<div class="card-content">{{Question}}</div>',
            'afmt': '{{FrontSide}}<hr id="answer"><div class="answer">{{Answer}}</div>'
                   '<div class="source">{{Source}}</div>',
        }],
        css='''
            .card { font-family: "Noto Sans SC", "Helvetica Neue", sans-serif;
                    font-size: 18px; text-align: center; color: #333; }
            .card-content { margin: 20px; line-height: 1.8; }
            .answer { margin: 20px; text-align: left; line-height: 1.8; font-size: 16px; }
            .source { margin-top: 20px; font-size: 12px; color: #999; text-align: right; }
            b { color: #1a73e8; }
            hr { border: 0; border-top: 1px solid #e0e0e0; }
        '''
    )

    cloze_model = genanki.Model(
        MODEL_ID + 1,
        'Android面试-Cloze填空',
        model_type=genanki.Model.CLOZE,
        fields=[
            {'name': 'Text'},
            {'name': 'Extra'},
        ],
        templates=[{
            'name': 'Cloze Card',
            'qfmt': '<div class="card-content">{{cloze:Text}}</div>',
            'afmt': '{{FrontSide}}<hr id="answer"><div class="source">{{Extra}}</div>',
        }],
        css='''
            .card { font-family: "Noto Sans SC", "Helvetica Neue", sans-serif;
                    font-size: 18px; text-align: center; color: #333; }
            .card-content { margin: 20px; line-height: 1.8; }
            .source { margin-top: 20px; font-size: 12px; color: #999; text-align: right; }
            .cloze { font-weight: bold; color: #1a73e8; }
            hr { border: 0; border-top: 1px solid #e0e0e0; }
        '''
    )

    # Group by deck
    decks = {}
    for i, card in enumerate(cards):
        deck_name = get_deck_name(card)
        if deck_name not in decks:
            deck_id = DECK_ROOT_ID + hash(deck_name) % 100000
            decks[deck_name] = {
                'deck': genanki.Deck(deck_id, deck_name),
                'cards': []
            }

        # Escape HTML
        def escape_html(text):
            text = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            text = text.replace('&amp;lt;', '&lt;').replace('&amp;gt;', '&gt;')  # fix double-escape
            # Restore safe HTML tags
            for tag in ['b', 'br', 'hr']:
                text = text.replace(f'&lt;{tag}&gt;', f'<{tag}>')
                text = text.replace(f'&lt;/{tag}&gt;', f'</{tag}>')
            return text

        if card['card_type'] == 'cloze':
            note = genanki.Note(
                model=cloze_model,
                fields=[card['front'], f"来源: {card['source']}"]
            )
        else:
            note = genanki.Note(
                model=basic_model,
                fields=[
                    card['front'],
                    escape_html(card['back']),
                    f"来源: {card['source']}"
                ]
            )

        # Add tags
        note.tags = card.get('tags', [])[:10]  # Limit tag count

        decks[deck_name]['cards'].append(note)

    # Add notes to decks
    for deck_info in decks.values():
        for note in deck_info['cards']:
            deck_info['deck'].add_note(note)

    # Build package
    all_decks = [d['deck'] for d in decks.values()]
    pkg = genanki.Package(all_decks)
    os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
    pkg.write_to_file(output_path)

    # Stats
    print(f"\n按牌组统计:")
    for name, info in sorted(decks.items(), key=lambda x: -len(x[1]['cards'])):
        print(f"  {name}: {len(info['cards'])} 张")

# ============================================================
# Main
# ============================================================
def main():
    print("=" * 60)
    print("合并卡片并重建 APKG")
    print("=" * 60)

    # 1. Load all sources
    print("\n[1/4] 加载卡片...")
    knowledge = load_knowledge_cards()
    interview = load_interview_cards()
    txt = load_txt_cards()

    print(f"  知识笔记AI: {len(knowledge)} 张")
    print(f"  面试题集: {len(interview)} 张")
    print(f"  TXT文件: {len(txt)} 张")

    all_cards = knowledge + interview + txt
    print(f"  合并总数: {len(all_cards)} 张")

    # 2. Quality filter
    print(f"\n[2/4] 质量过滤...")
    filtered = quality_filter(all_cards)
    print(f"  过滤后: {len(filtered)} (移除 {len(all_cards) - len(filtered)})")

    # 3. Deduplicate
    print(f"\n[3/4] 去重...")
    final = deduplicate(filtered, SIMILARITY_THRESHOLD)
    dup_count = len(filtered) - len(final)
    print(f"  去重后: {len(final)} (移除 {dup_count} 张重复)")

    # 4. Build APKG
    print(f"\n[4/4] 生成 APKG...")
    build_apkg(final, "output/Android面试卡组.apkg")

    # Summary
    print(f"\n{'=' * 60}")
    print(f"✅ 重建完成！")
    print(f"   总卡片: {len(final)} 张")
    print(f"   知识笔记: {len(knowledge)} → {len([c for c in final if '核心知识点笔记' in c['source']])} 张（去重后）")
    print(f"   面试题集: {len(interview)} → {len([c for c in final if '阿里巴巴' in c['source']])} 张（去重后）")
    print(f"   TXT文件: {len(txt)} → {len([c for c in final if '.txt' in c['source']])} 张（去重后）")
    print(f"   输出: output/Android面试卡组.apkg")
    print(f"{'=' * 60}")

if __name__ == '__main__':
    main()
