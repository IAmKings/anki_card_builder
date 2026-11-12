import json
import tempfile
import unittest
from pathlib import Path

from ankicards.cli import main
from ankicards.review import build_payload, render_html, write_review
from ankicards.schema import load_spec


def make_deck(root: Path) -> Path:
    deck = root / "deck"
    (deck / "cards").mkdir(parents=True)
    (deck / "deck.json").write_text(json.dumps({"name": "测试牌组", "source_kind": "pdf"}), encoding="utf-8")
    card = {"key": "aaaaaaaaaaaa", "type": "qa", "q": "测试问题？", "a": "测试答案内容。", "source": "page:1"}
    (deck / "cards" / "01.json").write_text(json.dumps({"deck": "01 测试", "cards": [card]}), encoding="utf-8")
    return deck


def make_plan(root: Path) -> Path:
    plan = {
        "version": 1,
        "deck": {"name": "测试牌组", "source_kind": "pdf"},
        "cards": [
            {"type": "cloze", "source_key": "aaaaaaaaaaaa", "text": "成立于 {{c1::1755}} 年。", "source_excerpt": "成立于 1755 年。"},
            {"type": "choice", "source_key": "aaaaaaaaaaaa", "stem": "测试问题？", "source_excerpt": "测试答案内容。",
             "answer_index": 0,
             "options": [{"text": "短", "origin": "same-deck"}, {"text": "一个明显很长的干扰项内容", "origin": "same-deck"},
                         {"text": "另一个很长的干扰项", "origin": "same-deck"}, {"text": "再来一个长干扰项", "origin": "same-deck"}]},
        ],
        "skipped": [{"source_key": "aaaaaaaaaaaa", "reason": "code_snippet"}],
    }
    path = root / "plan.json"
    path.write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
    return path


class ReviewTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.deck = make_deck(self.root)
        self.plan = make_plan(self.root)

    def tearDown(self):
        self.tmp.cleanup()

    def test_payload_counts_and_flags(self):
        spec = load_spec(self.deck)
        payload = build_payload(json.loads(self.plan.read_text()), spec)
        self.assertEqual(payload["counts"]["cloze"], 1)
        self.assertEqual(payload["counts"]["choice"], 1)
        self.assertEqual(payload["skipped"], {"code_snippet": 1})
        choice = [c for c in payload["cards"] if c["type"] == "choice"][0]
        self.assertGreater(choice["ratio"], 2)
        self.assertTrue(any(f["level"] == "bad" for f in choice["flags"]))
        self.assertEqual(choice["source"]["q"], "测试问题？")

    def test_html_is_self_contained(self):
        spec = load_spec(self.deck)
        html = render_html(build_payload(json.loads(self.plan.read_text()), spec))
        self.assertIn("application/json", html)
        self.assertIn("测试问题", html)
        self.assertNotIn("http://", html)
        self.assertNotIn("https://", html)

    def test_write_review_and_cli(self):
        out, counts = write_review(self.plan, self.deck)
        self.assertTrue(out.exists())
        self.assertEqual(counts["choice"], 1)
        out2 = self.root / "cli.html"
        self.assertEqual(main(["derive", "review", str(self.plan), "--deck", str(self.deck), "--out", str(out2)]), 0)
        self.assertTrue(out2.read_text(encoding="utf-8").startswith("<!DOCTYPE html>"))


if __name__ == "__main__":
    unittest.main()
