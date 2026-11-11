import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from ankicards import cli
from ankicards.derive import (
    DeriveOptions,
    build_deck,
    build_plan,
    check_plan,
    compile_plan,
    derive_key,
    load_derived_plan,
    plain,
    summary,
)
from ankicards.schema import load_spec


def write_deck(root: Path, cards: list[dict], name: str = "派生测试") -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "deck.json").write_text(
        json.dumps({"name": name, "source_kind": "md"}, ensure_ascii=False), encoding="utf-8")
    cards_dir = root / "cards"
    cards_dir.mkdir(exist_ok=True)
    (cards_dir / "01.json").write_text(
        json.dumps({"deck": "", "cards": cards}, ensure_ascii=False), encoding="utf-8")
    return root


BASE_CARDS = [
    {
        "type": "qa",
        "q": "HashMap 的默认初始容量是多少？",
        "a": "默认初始容量是<b>16</b>个桶，负载因子 0.75。",
        "tags": ["kind:fact"],
    },
    {
        "type": "qa",
        "q": "ArrayList 扩容时复制要多久？",
        "a": "每次扩容为原来的 1.5 倍，复制耗时在 10 秒以内。",
        "tags": ["kind:fact"],
    },
    {
        "type": "qa",
        "q": "JVM 由哪些部分组成？",
        "a": "类加载器、运行时数据区、执行引擎，共 3 个部分。",
        "tags": ["kind:claim"],
    },
    {
        "type": "qa",
        "q": "GC 的作用是什么？",
        "a": "回收不再使用的对象，避免一次性占用 100 MB 的内存。",
        "tags": ["kind:fact"],
    },
    {
        "type": "qa",
        "q": "线程池的核心参数有哪些？",
        "a": "核心线程数、最大线程数、队列容量，共 7 个参数。",
        "tags": ["kind:procedure"],
    },
]


class PlainTextTest(unittest.TestCase):
    def test_strips_html_and_is_idempotent(self):
        raw = "默认<b>16</b><br>负载因子&lt;b&gt;0.75&lt;/b&gt;"
        first = plain(raw)
        self.assertEqual(first, plain(first))
        self.assertNotIn("<", first)
        self.assertIn("16", first)


class BuildPlanTest(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.root = write_deck(Path(self.tmp.name) / "src", BASE_CARDS)
        self.spec = load_spec(self.root)

    def tearDown(self):
        self.tmp.cleanup()

    def test_cloze_uses_verbatim_fragment(self):
        plan = build_plan(self.spec, None, DeriveOptions())
        answers = {plain(c["q"]): plain(c["a"]) for c in BASE_CARDS}
        cloze = [c for c in plan["cards"] if c["type"] == "cloze"]
        self.assertTrue(cloze)
        for card in cloze:
            self.assertIn(card["source_excerpt"], answers[card["source_q"]])
            self.assertIn("{{c1::", card["text"])
            self.assertIn("原题：", card["extra"])

    def test_choice_has_exactly_one_correct_option(self):
        plan = build_plan(self.spec, None, DeriveOptions(options=4))
        choices = [c for c in plan["cards"] if c["type"] == "choice"]
        self.assertTrue(choices)
        for card in choices:
            self.assertEqual(len(card["options"]), 4)
            self.assertTrue(0 <= card["answer_index"] < 4)
            self.assertTrue(card["options"][card["answer_index"]]["text"])

    def test_check_passes_on_generated_plan(self):
        plan = build_plan(self.spec, None, DeriveOptions())
        report, stats = check_plan(plan, self.spec)
        self.assertTrue(report.ok, report.errors)
        self.assertGreater(stats["cloze"], 0)

    def test_tampered_excerpt_is_rejected(self):
        plan = build_plan(self.spec, None, DeriveOptions())
        cloze = next(c for c in plan["cards"] if c["type"] == "cloze")
        cloze["source_excerpt"] = "完全不在原文里的句子"
        report, _ = check_plan(plan, self.spec)
        self.assertFalse(report.ok)
        self.assertTrue(any("逐字子串" in e for e in report.errors))

    def test_duplicate_options_are_rejected(self):
        plan = build_plan(self.spec, None, DeriveOptions())
        choice = next(c for c in plan["cards"] if c["type"] == "choice")
        index = (choice["answer_index"] + 1) % 4
        choice["options"][index]["text"] = choice["options"][choice["answer_index"]]["text"]
        report, _ = check_plan(plan, self.spec)
        self.assertFalse(report.ok)

    def test_model_option_needs_permission(self):
        plan = build_plan(self.spec, None, DeriveOptions())
        choice = next(c for c in plan["cards"] if c["type"] == "choice")
        index = (choice["answer_index"] + 1) % 4
        choice["options"][index] = {"text": "模型编的干扰项", "origin": "model"}
        report, stats = check_plan(plan, self.spec)
        self.assertTrue(report.ok)
        self.assertTrue(report.warnings)
        self.assertEqual(stats["model_options"], 1)
        report2, _ = check_plan(plan, self.spec, allow_model=False)
        self.assertTrue(report2.ok)

    def test_derive_key_is_stable(self):
        first = derive_key("牌组", "填空", "abc123", 0)
        self.assertEqual(first, derive_key("牌组", "填空", "abc123", 0))
        self.assertNotEqual(first, derive_key("牌组", "填空", "abc123", 1))
        self.assertRegex(first, r"^[0-9a-f]{12}$")

    def test_compile_writes_derived_cards_and_keeps_source(self):
        plan = build_plan(self.spec, None, DeriveOptions())
        out = Path(self.tmp.name) / "out"
        before = {
            p.name: p.read_text(encoding="utf-8")
            for p in sorted((self.root / "cards").glob("*.json"))
        }
        compile_plan(plan, self.spec, out)
        cards = []
        for path in sorted((out / "cards").glob("*.json")):
            cards.extend(json.loads(path.read_text(encoding="utf-8"))["cards"])
        self.assertTrue(any(c["type"] == "cloze" for c in cards))
        self.assertTrue(any(c["type"] == "qa" and "A. " in c["q"] for c in cards))
        self.assertTrue(all("key" in c for c in cards))
        after = {
            p.name: p.read_text(encoding="utf-8")
            for p in sorted((self.root / "cards").glob("*.json"))
        }
        self.assertEqual(before, after)


class CliTest(unittest.TestCase):
    def test_dry_run_and_compile_roundtrip(self):
        with TemporaryDirectory() as tmp:
            root = write_deck(Path(tmp) / "src", BASE_CARDS)
            code = cli.main(["derive", "plan", "--deck", str(root), "--dry-run"])
            self.assertEqual(code, 0)
            plan_path = Path(tmp) / "plan_derive.json"
            self.assertEqual(cli.main([
                "derive", "plan", "--deck", str(root), "--out", str(plan_path)]), 0)
            self.assertTrue(plan_path.exists())
            self.assertEqual(cli.main([
                "derive", "check", str(plan_path), "--deck", str(root)]), 0)
            out = Path(tmp) / "derived"
            self.assertEqual(cli.main([
                "derive", "compile", str(plan_path), "--deck", str(root),
                "--out", str(out)]), 0)
            self.assertTrue((out / "deck.json").exists())
            self.assertEqual(cli.main(["derive", "report", str(plan_path)]), 0)


class GateTest(unittest.TestCase):
    """两道确定性闸：代码块/压平表格不出题，挖空不切 token。"""

    def _plan_for(self, answer: str):
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        cards = [{"type": "qa", "q": "这张卡问的是什么？", "a": answer,
                  "tags": ["kind:fact"]},
                 {"type": "qa", "q": "另一张卡问的是什么？", "a": "这是一个用来当干扰项的普通答案。",
                  "tags": ["kind:fact"]},
                 {"type": "qa", "q": "第三张卡问的是什么？", "a": "这是第二个用来当干扰项的答案。",
                  "tags": ["kind:fact"]},
                 {"type": "qa", "q": "第四张卡问的是什么？", "a": "这是第三个用来当干扰项的答案。",
                  "tags": ["kind:fact"]}]
        root = write_deck(Path(tmp.name) / "src", cards)
        return build_plan(load_spec(root), None, DeriveOptions())

    def test_code_answer_is_skipped(self):
        plan = self._plan_for("// 推断为 Stream // 限制：只能用于局部变量")
        self.assertEqual([c for c in plan["cards"] if c["source_q"] == "这张卡问的是什么？"], [])
        reasons = {s["reason"] for s in plan["skipped"]}
        self.assertIn("code_snippet", reasons)

    def test_flattened_table_is_skipped(self):
        plan = self._plan_for("参数 | 调用次数 | 用途 | factory 一次 | update 多次")
        mine = [c for c in plan["cards"] if c["source_q"] == "这张卡问的是什么？"]
        self.assertEqual(mine, [])

    def test_span_glued_to_ascii_is_not_blanked(self):
        plan = self._plan_for("使用 NetworkType.CONNECTED 判断网络连接状态，失败时重试两次。")
        cloze = [c for c in plan["cards"]
                 if c["type"] == "cloze" and c["source_q"] == "这张卡问的是什么？"]
        self.assertEqual(cloze, [])


if __name__ == "__main__":
    unittest.main()
