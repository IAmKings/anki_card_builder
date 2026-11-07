"""适配器回归测试：MD → DeckData 的形状与数量。"""

import json
import tempfile
import unittest
from pathlib import Path

from ankicards.adapters import ADAPTERS, from_mqtt_md, write_deck

SAMPLE = """## 一、基础概念（1-2）

1. **MQTT**：消息队列遥测传输协议，基于发布/订阅模式。
2. **Broker**：消息代理服务器，负责转发消息给订阅者。
"""


class MqttAdapterTest(unittest.TestCase):
    def test_sections_and_card_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "sample.md"
            src.write_text(SAMPLE, encoding="utf-8")
            deck = from_mqtt_md(src)
            self.assertEqual(deck.name, "MQTT协议")
            self.assertEqual(deck.card_count, 4)          # 2 个知识点 ×（问答 + 选择题）
            self.assertEqual(len(deck.sections), 1)
            cards = next(iter(deck.sections.values()))
            self.assertEqual(sum(1 for c in cards if "正确答案：" in c["a"]), 2)
            self.assertTrue(all(c["source"] for c in cards))

    def test_registry_has_both_adapters(self):
        self.assertIn("android-md", ADAPTERS)
        self.assertIn("mqtt-md", ADAPTERS)

    def test_write_deck_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "sample.md"
            src.write_text(SAMPLE, encoding="utf-8")
            out = write_deck(from_mqtt_md(src), Path(tmp) / "deck")
            self.assertTrue((out / "deck.json").exists())
            self.assertEqual(len(list((out / "cards").glob("*.json"))), 1)
            manifest = json.loads((out / "deck.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["name"], "MQTT协议")
            self.assertEqual(manifest["source_kind"], "md")


if __name__ == "__main__":
    unittest.main()
