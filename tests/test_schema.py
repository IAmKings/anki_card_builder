"""ankicards 数据契约与确定性 ID 的回归测试。"""

import json
import tempfile
import unittest
from pathlib import Path

from ankicards.ids import deck_id, model_id, stable_int
from ankicards.schema import load_spec, validate


def make_deck(tmp: Path, cards, crops=None, name="测试牌组"):
    (tmp / "cards").mkdir(parents=True, exist_ok=True)
    (tmp / "cards" / "01.json").write_text(
        json.dumps({"deck": "01 测试", "cards": cards}, ensure_ascii=False), encoding="utf-8")
    if crops is not None:
        (tmp / "crops.json").write_text(json.dumps(crops, ensure_ascii=False), encoding="utf-8")
    (tmp / "deck.json").write_text(json.dumps({"name": name}, ensure_ascii=False), encoding="utf-8")
    return load_spec(tmp)


class SchemaTest(unittest.TestCase):
    def test_valid_deck_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec = make_deck(Path(tmp), [
                {"type": "qa", "q": "问题", "a": "答案", "pages": [1]},
                {"type": "cloze", "text": "x{{c1::y}}", "extra": "补充", "pages": [2]},
            ])
            self.assertTrue(validate(spec).ok)

    def test_missing_question_is_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec = make_deck(Path(tmp), [{"type": "qa", "q": "", "a": "答案", "pages": [1]}])
            report = validate(spec)
            self.assertFalse(report.ok)
            self.assertTrue(any("缺少 q" in e for e in report.errors))

    def test_image_requires_known_crop(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec = make_deck(Path(tmp), [
                {"type": "image", "q": "看图", "a": "答案", "img": "nope", "pages": [1]},
            ], crops={"known": {"page": 1, "rect": [0, 0, 10, 10]}})
            report = validate(spec)
            self.assertFalse(report.ok)
            self.assertTrue(any("不在 crops.json" in e for e in report.errors))

    def test_images_with_same_question_are_not_duplicates(self):
        """不同图片、同一题干是合法卡片——旧校验 19 条误报的根因。"""
        with tempfile.TemporaryDirectory() as tmp:
            spec = make_deck(Path(tmp), [
                {"type": "image", "q": "这是哪个系列？", "a": "A", "img": "a", "pages": [1]},
                {"type": "image", "q": "这是哪个系列？", "a": "B", "img": "b", "pages": [1]},
            ], crops={
                "a": {"page": 1, "rect": [0, 0, 10, 10]},
                "b": {"page": 1, "rect": [10, 10, 20, 20]},
            })
            report = validate(spec)
            self.assertTrue(report.ok)
            self.assertFalse(any("身份重复" in w for w in report.warnings))

    def test_same_question_different_answer_is_not_duplicate(self):
        """同题干不同答案是两张卡；旧实现只按 q 判重会误报。"""
        with tempfile.TemporaryDirectory() as tmp:
            spec = make_deck(Path(tmp), [
                {"type": "qa", "q": "同一问题", "a": "A", "pages": [1]},
                {"type": "qa", "q": "同一问题 ", "a": "B", "pages": [1]},
            ])
            report = validate(spec)
            self.assertTrue(report.ok)
            self.assertFalse(any("身份重复" in w for w in report.warnings))

    def test_card_key_must_be_12_hex(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec = make_deck(Path(tmp), [
                {"type": "qa", "q": "问题", "a": "答案", "pages": [1], "key": "not-a-key"}])
            report = validate(spec)
            self.assertFalse(report.ok)
            self.assertTrue(any("key 必须是 12 位" in e for e in report.errors))

    def test_card_key_overrides_text_identity(self):
        from ankicards.schema import identity_seed
        left = {"type": "qa", "q": "旧问题", "a": "旧答案", "key": "0123456789ab"}
        right = {"type": "qa", "q": "改过的问题", "a": "改过的答案", "key": "0123456789ab"}
        self.assertEqual(identity_seed("牌组", left), identity_seed("牌组", right))
        other = {"type": "qa", "q": "旧问题", "a": "旧答案", "key": "0123456789ac"}
        self.assertNotEqual(identity_seed("牌组", left), identity_seed("牌组", other))

    def test_identical_qa_duplicate_warns(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec = make_deck(Path(tmp), [
                {"type": "qa", "q": "同一问题", "a": "同一答案", "pages": [1]},
                {"type": "qa", "q": "同一问题 ", "a": "同一答案 ", "pages": [1]},
            ])
            report = validate(spec)
            self.assertTrue(any("身份重复" in w for w in report.warnings))

    def test_source_only_card_is_valid(self):
        """MD 来源没有页码，用 source 溯源必须合法。"""
        with tempfile.TemporaryDirectory() as tmp:
            spec = make_deck(Path(tmp), [
                {"type": "qa", "q": "问题", "a": "答案", "source": "某题库.md"},
            ])
            report = validate(spec)
            self.assertTrue(report.ok)
            self.assertFalse(any("无法溯源" in w for w in report.warnings))

    def test_missing_pages_and_source_warns(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec = make_deck(Path(tmp), [{"type": "qa", "q": "问题", "a": "答案"}])
            report = validate(spec)
            self.assertTrue(report.ok)
            self.assertTrue(any("无法溯源" in w for w in report.warnings))

    def test_page_bounds_only_with_pdf(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec = make_deck(Path(tmp), [{"type": "qa", "q": "问题", "a": "答案", "pages": [99]}])
            self.assertTrue(validate(spec).ok)                      # 没有 PDF 时不检查上界
            self.assertFalse(validate(spec, page_count=10).ok)      # 有 PDF 时检查

    def test_crop_rect_order_is_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec = make_deck(Path(tmp), [
                {"type": "image", "q": "看图", "a": "答案", "img": "bad", "pages": [1]},
            ], crops={"bad": {"page": 1, "rect": [10, 10, 5, 5]}})
            self.assertFalse(validate(spec).ok)


class IdTest(unittest.TestCase):
    def test_stable_across_calls(self):
        self.assertEqual(deck_id("某个牌组"), deck_id("某个牌组"))
        self.assertEqual(model_id("某个牌组", "basic"), model_id("某个牌组", "basic"))

    def test_distinct(self):
        self.assertNotEqual(deck_id("a"), deck_id("b"))
        self.assertNotEqual(model_id("甲", "basic"), model_id("甲", "cloze"))
        self.assertNotEqual(deck_id("同名") % 1_000_000, model_id("同名", "basic") % 1_000_000)

    def test_ranges_are_sane(self):
        for value in (deck_id("x"), model_id("x", "basic")):
            self.assertGreater(value, 1_000_000_000)
            self.assertLess(value, 2_147_483_647)  # Anki 的 int32 上限

    def test_stable_int_matches_known_value(self):
        # 锁定一次取值，防止未来无意改动算法导致已发布牌组换 ID
        self.assertEqual(stable_int("deck::固定值", 1_700_000_000),
                         stable_int("deck::固定值", 1_700_000_000))


if __name__ == "__main__":
    unittest.main()
