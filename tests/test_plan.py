"""plan.json 契约的测试：引用锚定、理由枚举、覆盖率、编译与 diff。"""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from ankicards.cli import main
from ankicards.ingest import load_ingest
from ankicards.plan import check_plan, compile_plan, diff_plan
from ankicards.schema import load_spec

LINES = [
    "部署手册",
    "1. **幂等**：同一请求重复执行结果一致。",
    "重试时必须带同一请求号。",
    "2. **端口**：默认监听 8080，生产需改。",
]
GROUPS = [
    {"id": "g1", "kind": "heading", "unit_locators": ["line:1"],
     "span": ["line:1", "line:1"], "locator": "line:1", "chars": 4},
    {"id": "g2", "kind": "point", "unit_locators": ["line:2", "line:3"],
     "span": ["line:2", "line:3"], "locator": "line:2-3", "chars": 30},
    {"id": "g3", "kind": "point", "unit_locators": ["line:4"],
     "span": ["line:4", "line:4"], "locator": "line:4", "chars": 20},
]

QUOTE_G2 = "1. **幂等**：同一请求重复执行结果一致。 重试时必须带同一请求号。"
QUOTE_G3 = "2. **端口**：默认监听 8080，生产需改。"


def write_manifest(path: Path) -> Path:
    units = [{"id": f"line:{i}", "line": i, "chars": len(text), "text": text}
             for i, text in enumerate(LINES, 1)]
    manifest = {"format": "txt", "source": "demo.txt", "source_sha256": None,
                "unit_kind": "line", "unit_count": len(units),
                "total_chars": sum(u["chars"] for u in units),
                "units": units, "groups": GROUPS, "warnings": [],
                "empty_lines": [], "encoding": "utf-8"}
    path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    return path


def card_g2(**overrides) -> dict:
    card = {"locator": "line:2-3", "quote": QUOTE_G2, "kind": "claim",
            "q": "重试时为什么必须带同一请求号？",
            "a": "为了让重复请求被幂等处理，结果保持一致。"}
    card.update(overrides)
    return card


def card_g3(**overrides) -> dict:
    card = {"locator": "line:4", "quote": QUOTE_G3, "kind": "claim",
            "q": "默认监听哪个端口？", "a": "8080。"}
    card.update(overrides)
    return card


def make_plan(cards=None, skipped=None, **deck) -> dict:
    info = {"name": "演示", "source_kind": "txt"}
    info.update(deck)
    return {"version": 1, "deck": info, "cards": cards or [],
            "skipped": skipped or []}


class PlanRulesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.manifest = self.dir / "demo.json"
        write_manifest(self.manifest)
        self.ingest = load_ingest(self.manifest)

    def check(self, plan: dict, **kwargs):
        return check_plan(plan, self.ingest, **kwargs)

    def test_valid_plan_passes(self) -> None:
        report, stats = self.check(make_plan([card_g2(), card_g3()]),
                                   min_coverage=0.6)
        self.assertEqual(report.errors, [])
        self.assertAlmostEqual(stats["coverage"], 2 / 3)

    def test_quote_must_be_verbatim_substring(self) -> None:
        report, _ = self.check(make_plan([card_g2(
            quote="同一请求重复执行的结果一致。")]))
        self.assertTrue(any("逐字子串" in error for error in report.errors))

    def test_quote_ignores_line_break_spaces(self) -> None:
        # PDF/Word 的换行会在任意位置插空格，手打引用不该因此被判成改写。
        report, _ = self.check(make_plan([card_g2(
            quote="1. **幂等**：同一请求重复执行结果一致。\n重试时必须带同一请求号。")]))
        self.assertEqual(report.errors, [])

    def test_numbers_ignore_thousand_separators(self) -> None:
        path = Path(self.tmp.name) / "comma.json"
        text = "年产量约2,500万枚。"
        manifest = {"format": "txt", "source": "c.txt", "source_sha256": None,
                    "unit_kind": "line", "unit_count": 1, "total_chars": len(text),
                    "units": [{"id": "line:1", "line": 1, "chars": len(text), "text": text}],
                    "groups": [{"id": "g1", "kind": "prose", "unit_locators": ["line:1"],
                                "span": ["line:1", "line:1"], "locator": "line:1",
                                "chars": len(text)}],
                    "warnings": [], "empty_lines": [], "encoding": "utf-8"}
        path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
        plan = make_plan([{"locator": "line:1", "quote": text,
                           "q": "年产量约多少？", "a": "2500 万枚。"}])
        report, _ = check_plan(plan, load_ingest(path))
        self.assertEqual(report.errors, [])

    def long_manifest(self, text: str, tail: str = "後記"):
        path = Path(self.tmp.name) / "long.json"
        units = [{"id": "line:1", "line": 1, "chars": len(text), "text": text},
                 {"id": "line:2", "line": 2, "chars": len(tail), "text": tail}]
        manifest = {"format": "txt", "source": "l.txt", "source_sha256": None,
                    "unit_kind": "line", "unit_count": 2,
                    "total_chars": len(text) + len(tail), "units": units,
                    "groups": [
                        {"id": "g1", "kind": "prose", "unit_locators": ["line:1"],
                         "span": ["line:1", "line:1"], "locator": "line:1", "chars": len(text)},
                        {"id": "g2", "kind": "prose", "unit_locators": ["line:2"],
                         "span": ["line:2", "line:2"], "locator": "line:2", "chars": len(tail)}],
                    "warnings": [], "empty_lines": [], "encoding": "utf-8"}
        path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
        return load_ingest(path)

    def test_essay_profile_allows_long_quote(self) -> None:
        text = "這是一段完整的散文論述，用來測試長引用。" * 20
        ingest = self.long_manifest(text)
        plan = make_plan([{"locator": "line:1", "quote": text,
                           "q": "作者怎麼說？", "a": "見引用。"}])
        report, _ = check_plan(plan, ingest, profile="essay")
        self.assertEqual(report.errors, [])
        report, _ = check_plan(plan, ingest)
        self.assertTrue(any("长度必须在 8–300" in error for error in report.errors))

    def test_essay_profile_adds_essay_skip_reasons(self) -> None:
        ingest = self.long_manifest("這是一段完整的散文論述，用來測試長引用。")
        plan = make_plan(skipped=[{"locator": "line:2", "reason": "anecdote"}])
        report, _ = check_plan(plan, ingest, profile="essay")
        self.assertEqual(report.errors, [])
        report, _ = check_plan(plan, ingest)
        self.assertTrue(any("必须是" in error for error in report.errors))
        report, _ = check_plan(plan, ingest, profile="novel")
        self.assertTrue(any("必须是" in error for error in report.errors))

    def test_unknown_profile_is_error(self) -> None:
        report, _ = self.check(make_plan([card_g2()]), profile="poem")
        self.assertTrue(any("profile" in error for error in report.errors))

    def test_numbers_must_come_from_quote(self) -> None:
        report, _ = self.check(make_plan([card_g3(a="9090 端口。")]))
        self.assertTrue(any("答案数字 9090" in error for error in report.errors))

    def test_question_label_numbers_are_not_card_facts(self) -> None:
        """真实讲义里问题常带编号（「案例 2」「第 4 节」），不是要背的数字。"""
        report, _ = self.check(make_plan([card_g3(q="案例 2：默认监听哪个端口？", a="8080。")]))
        self.assertEqual(report.errors, [])
        self.assertEqual(report.warnings, [])

    def test_number_in_question_is_only_a_warning(self) -> None:
        report, _ = self.check(make_plan([card_g3(q="超时是多少，30 秒吗？", a="8080。")]))
        self.assertEqual(report.errors, [])
        self.assertTrue(any("问题里的数字 30" in warning for warning in report.warnings))

    def test_bad_key_format_is_error(self) -> None:
        report, _ = self.check(make_plan([card_g2(key="ABC")]))
        self.assertTrue(any("12 位小写十六进制" in error for error in report.errors))

    def test_quote_length_bounds(self) -> None:
        report, _ = self.check(make_plan([card_g2(quote="幂等")]))
        self.assertTrue(any("长度必须在" in error for error in report.errors))

    def test_locator_must_exist(self) -> None:
        report, _ = self.check(make_plan([card_g2(locator="line:99")]))
        self.assertTrue(any("定位不在 ingest 产物中" in error for error in report.errors))

    def test_skip_reason_must_be_enum(self) -> None:
        report, _ = self.check(make_plan(
            [card_g2(), card_g3()],
            [{"locator": "line:1", "reason": "因为它是标题"}]))
        self.assertTrue(any("reason: 必须是" in error for error in report.errors))

    def test_skip_reason_semantic_is_allowed(self) -> None:
        report, _ = self.check(make_plan(
            [card_g2(), card_g3()],
            [{"locator": "line:1", "reason": "heading"}]))
        self.assertEqual(report.errors, [])

    def test_entries_must_not_overlap(self) -> None:
        report, _ = self.check(make_plan([card_g2(), card_g2()]))
        self.assertTrue(any("引用重叠" in error for error in report.errors))

    def test_same_group_allows_disjoint_quotes(self) -> None:
        first = card_g2(quote="1. **幂等**：同一请求重复执行结果一致。",
                        q="什么叫幂等？", a="同一请求重复执行结果一致。")
        second = card_g2(quote="重试时必须带同一请求号。",
                         q="重试时要带什么？", a="同一请求号。")
        report, stats = self.check(make_plan([first, second]))
        self.assertEqual(report.errors, [])
        self.assertEqual(stats["cards"], 2)

    def test_kind_missing_is_warning(self) -> None:
        card = card_g2()
        card.pop("kind")
        report, _ = self.check(make_plan([card]))
        self.assertEqual(report.errors, [])
        self.assertTrue(any("建议标注卡型" in warning for warning in report.warnings))

    def test_kind_must_be_known(self) -> None:
        report, _ = self.check(make_plan([card_g2(kind="story")]))
        self.assertTrue(any("必须是 claim/style/phrase/fact" in e for e in report.errors))

    def test_phrase_quote_must_stay_short(self) -> None:
        long_line = "1. **金句**：" + "把日子过成一句话" * 8
        units = [{"id": "line:1", "line": 1, "chars": len(long_line),
                  "text": long_line}]
        groups = [{"id": "g1", "kind": "point", "unit_locators": ["line:1"],
                   "span": ["line:1", "line:1"], "locator": "line:1",
                   "chars": len(long_line)}]
        manifest = {"format": "txt", "source": "long.txt", "source_sha256": None,
                    "unit_kind": "line", "unit_count": 1,
                    "total_chars": len(long_line), "units": units,
                    "groups": groups, "warnings": []}
        path = self.dir / "long.json"
        path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
        ingest = load_ingest(path)
        card = {"locator": "line:1", "quote": long_line, "kind": "phrase",
                "q": "这句话怎么背？", "a": "整句记住。"}
        report = check_plan(make_plan([card]), ingest)[0]
        self.assertTrue(any("金句卡的 quote" in warning for warning in report.warnings))

    def test_style_quote_must_be_long_enough(self) -> None:
        card = card_g2(quote="同一请求重复执行", kind="style",
                       q="这句话的写法有什么特点？", a="用短句下定义。")
        report, _ = self.check(make_plan([card]))
        self.assertTrue(any("文风卡的 quote" in warning for warning in report.warnings))

    def test_fact_quote_needs_a_number(self) -> None:
        card = card_g2(quote="重试时必须带同一请求号。", kind="fact",
                       q="重试时对请求号有什么要求？", a="必须带同一请求号。")
        report, _ = self.check(make_plan([card]))
        self.assertTrue(any("事实卡的 quote 里没有数字" in w for w in report.warnings))

    def test_claim_question_should_be_a_question(self) -> None:
        report, _ = self.check(make_plan([card_g2(q="重试时带同一请求号", a="原因如上。")]))
        self.assertTrue(any("观点卡的问题建议写成问句" in w for w in report.warnings))

    def test_coverage_threshold(self) -> None:
        report, stats = self.check(make_plan([card_g2()]), min_coverage=1.0)
        self.assertEqual(stats["covered"], 1)
        self.assertTrue(any("低于阈值" in error for error in report.errors))

    def test_invented_identifier_warns(self) -> None:
        report, _ = self.check(make_plan([card_g2(
            q="Kubernetes 里怎么保证幂等？")]))
        self.assertEqual(report.errors, [])
        self.assertTrue(any("Kubernetes" in warning for warning in report.warnings))

    def test_empty_plan_errors(self) -> None:
        report, _ = self.check(make_plan([]))
        self.assertTrue(any("既没有卡片也没有未出卡记录" in e for e in report.errors))

    def test_skip_only_plan_is_allowed_with_warning(self) -> None:
        plan = make_plan([], [{"locator": "line:1", "reason": "heading"},
                              {"locator": "line:2-3", "reason": "step_not_concept"},
                              {"locator": "line:4", "reason": "low_value"}])
        report, stats = self.check(plan, min_coverage=1.0)
        self.assertEqual(report.errors, [])
        self.assertTrue(any("没有卡片" in w for w in report.warnings))
        self.assertEqual(stats["coverage"], 1.0)


class PlanCompileTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.manifest = write_manifest(self.dir / "demo.json")
        self.ingest = load_ingest(self.manifest)
        self.out = self.dir / "deck"

    def test_compile_records_kind_as_tag(self) -> None:
        out = self.dir / "deck"
        report, _, path = compile_plan(make_plan([card_g2()]), self.ingest, out)
        self.assertFalse(report.errors)
        cards = json.loads((path / "cards" / "01.json").read_text(encoding="utf-8"))
        self.assertIn("kind:claim", cards["cards"][0]["tags"])

    def test_compile_writes_cards_and_ledger(self) -> None:
        plan = make_plan([card_g2(), card_g3()],
                         [{"locator": "line:1", "reason": "heading",
                           "note": "标题只做子牌组名"}])
        report, _, out = compile_plan(plan, self.ingest, self.out)
        self.assertEqual(report.errors, [])
        self.assertIsNotNone(out)
        spec = load_spec(self.out)
        cards = [card for _, _, card in spec.iter_cards()]
        self.assertEqual(len(cards), 2)
        first = cards[0]
        self.assertEqual(first["source"], "line:2-3")
        self.assertNotIn("quote", first)      # quote 只活在 plan.json 里
        report_json = json.loads((self.out / "import-report.json").read_text(encoding="utf-8"))
        self.assertEqual(report_json["skipped_by_reason"], {"heading": 1})
        self.assertEqual(report_json["cards"], 2)

    def test_compile_with_key_is_stable(self) -> None:
        out = Path(self.tmp.name) / "deckkey"
        plan = make_plan([card_g2(), card_g3()])
        report, _, _ = compile_plan(plan, self.ingest, out, with_key=True)
        self.assertTrue(report.ok)
        cards = json.loads((out / "cards" / "01.json").read_text(encoding="utf-8"))["cards"]
        keys = [card["key"] for card in cards]
        self.assertEqual(len(keys), 2)
        self.assertEqual(len(set(keys)), 2)
        for key in keys:
            self.assertRegex(key, r"^[0-9a-f]{12}$")

        # 同一定位重跑，只改措辞：key 不变（Anki 里仍是同一张卡）
        edited = make_plan([card_g2(q="同一请求为什么要幂等？",
                                    a="重复执行的结果必须一致。"),
                            card_g3()])
        report2, _, _ = compile_plan(edited, self.ingest, out, force=True, with_key=True)
        self.assertTrue(report2.ok)
        cards2 = json.loads((out / "cards" / "01.json").read_text(encoding="utf-8"))["cards"]
        self.assertEqual(keys, [card["key"] for card in cards2])

    def test_compile_without_key_writes_no_key(self) -> None:
        out = Path(self.tmp.name) / "deckplain"
        report, _, _ = compile_plan(make_plan([card_g2()]), self.ingest, out)
        self.assertTrue(report.ok)
        cards = json.loads((out / "cards" / "01.json").read_text(encoding="utf-8"))["cards"]
        self.assertNotIn("key", cards[0])

    def test_compile_refuses_on_error(self) -> None:
        report, _, out = compile_plan(make_plan([card_g2(quote="改写过的句子")]),
                                      self.ingest, self.out)
        self.assertFalse(report.ok)
        self.assertIsNone(out)
        self.assertFalse(self.out.exists())

    def test_diff_reports_changes(self) -> None:
        plan = make_plan([card_g2(), card_g3()], [{"locator": "line:1", "reason": "heading"}])
        compile_plan(plan, self.ingest, self.out)
        same = diff_plan(plan, self.out)
        self.assertEqual(same["added"], [])
        self.assertEqual(same["removed"], [])
        self.assertEqual(same["changed"], [])

        edited = make_plan([card_g2(), card_g3(a="8080，生产环境要改。"),
                            card_g3(locator="line:4", q="生产环境要改什么？")])
        result = diff_plan(edited, self.out)
        self.assertTrue(result["added"])
        self.assertTrue(result["changed"])

    def test_cli_check_exit_codes(self) -> None:
        plan_path = self.dir / "plan.json"
        plan_path.write_text(json.dumps(make_plan([card_g2(), card_g3()]),
                                        ensure_ascii=False), encoding="utf-8")
        self.assertEqual(main(["plan", "check", str(plan_path),
                               "--ingest", str(self.manifest)]), 0)
        plan_path.write_text(json.dumps(make_plan([card_g2(quote="改写过")]),
                                        ensure_ascii=False), encoding="utf-8")
        self.assertEqual(main(["plan", "check", str(plan_path),
                               "--ingest", str(self.manifest)]), 1)


if __name__ == "__main__":
    unittest.main()
