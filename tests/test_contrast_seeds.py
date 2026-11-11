import importlib.util
import json
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "contrast_seeds.py"
spec = importlib.util.spec_from_file_location("contrast_seeds", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class SplitItemsTest(unittest.TestCase):
    def test_reads_labelled_bullets(self):
        text = ("强引用（StrongReference）：绝不回收。• "
                "软引用（SoftReference）：OOM 前回收。")
        items = module.split_items(text)
        self.assertEqual([i["label"] for i in items],
                         ["强引用（StrongReference）", "软引用（SoftReference）"])

    def test_skips_abstract_labels(self):
        items = module.split_items("性能好：数据只需拷贝一次。• 安全性高：内核检查 UID。")
        self.assertEqual(items, [])

    def test_skips_untagged_text(self):
        self.assertEqual(module.split_items("没有冒号分隔的一段话。"), [])


class ItemPairsTest(unittest.TestCase):
    def test_pairs_adjacent_items_and_caps(self):
        cards = [{
            "key": "k1", "q": "引用类型有哪些？",
            "a": ("强引用（StrongReference）：绝不回收。• "
                  "软引用（SoftReference）：OOM 前回收。• "
                  "弱引用（WeakReference）：GC 就回收。"),
        }]
        pairs = module.pick_item_pairs(cards, per_card=2)
        self.assertEqual(len(pairs), 2)
        self.assertEqual(pairs[0]["left"]["label"], "强引用（StrongReference）")
        self.assertEqual(pairs[0]["right"]["label"], "软引用（SoftReference）")
        self.assertIn("有什么区别", pairs[0]["prompt"])
        self.assertEqual(pairs[0]["context"], "引用类型有哪些？")

    def test_no_items_no_pairs(self):
        self.assertEqual(module.pick_item_pairs([{"key": "k", "q": "q", "a": "一段话"}]), [])


class LoadSeedsTest(unittest.TestCase):
    def test_rejects_bad_shape(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "seeds.json"
            path.write_text(json.dumps({"version": 2, "cards": []}), encoding="utf-8")
            with self.assertRaises(SystemExit):
                module.load_seeds(path)


if __name__ == "__main__":
    unittest.main()
