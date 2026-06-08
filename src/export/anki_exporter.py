"""Anki Exporter module.

Exports flashcards to Anki .apkg format using genanki.
Also provides HTML escaping utilities (from rebuild_apkg.py).
"""

import logging
import os
import re
from pathlib import Path
from typing import List, Dict, Any

import genanki

from ..config import CONFIG
from ..models import Flashcard

log = logging.getLogger(__name__)


def escape_html(text: str) -> str:
    """Escape HTML special characters while preserving safe tags.

    From rebuild_apkg.py.
    """
    text = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    text = text.replace('&amp;lt;', '&lt;').replace('&amp;gt;', '&gt;')
    for tag in ['b', 'br', 'hr']:
        text = text.replace(f'&lt;{tag}&gt;', f'<{tag}>')
        text = text.replace(f'&lt;/{tag}&gt;', f'</{tag}>')
    return text


class AnkiExporter:
    """Export flashcards to Anki .apkg format using genanki."""

    def __init__(self):
        self.models = self._create_models()
        self.decks: Dict[str, Any] = {}

    def _create_models(self) -> Dict:
        """Create genanki models for basic and cloze card types."""
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

        deck_list = list(self.decks.values())
        package = genanki.Package(deck_list)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        package.write_to_file(str(output_path))

        log.info(f"Successfully exported to {output_path}")
        log.info(f"Total decks: {len(self.decks)}")
        for name, d in sorted(self.decks.items()):
            log.info(f"  Deck: {name} ({len(d.notes)} notes)")

        return str(output_path)

    @staticmethod
    def build_apkg_from_dicts(cards: List[Dict], output_path: str) -> str:
        """Build .apkg from dict-based cards (from rebuild_apkg.py compatibility)."""
        from ..processing.deduplicator import Deduplicator

        MODEL_ID = 1607392319
        DECK_ROOT_ID = 2059400110

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

        def get_deck_name(card):
            tags = [t.lower() for t in card.get('tags', [])]
            tag_str = ' '.join(tags)
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

            if matches(java_kw):
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

        decks = {}
        for card in cards:
            deck_name = get_deck_name(card)
            if deck_name not in decks:
                deck_id = DECK_ROOT_ID + hash(deck_name) % 100000
                decks[deck_name] = {
                    'deck': genanki.Deck(deck_id, deck_name),
                    'cards': []
                }

            if card.get('card_type') == 'cloze':
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

            note.tags = card.get('tags', [])[:10]
            decks[deck_name]['cards'].append(note)

        for deck_info in decks.values():
            for note in deck_info['cards']:
                deck_info['deck'].add_note(note)

        all_decks = [d['deck'] for d in decks.values()]
        pkg = genanki.Package(all_decks)
        os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
        pkg.write_to_file(output_path)

        log.info(f"Built .apkg at {output_path}")
        for name, info in sorted(decks.items(), key=lambda x: -len(x[1]['cards'])):
            log.info(f"  {name}: {len(info['cards'])} cards")

        return output_path
