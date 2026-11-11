"""plan.json 契约的测试：引用锚定、理由枚举、覆盖率、编译与 diff。"""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from ankicards.cli import main
from ankicards.ingest import IngestData, load_ingest
from ankicards.errors import CardError
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


class PageRangeTest(unittest.TestCase):
    """P7a：PDF 跨页段落用 page:N-M 引用，不再被迫按页截断。"""

    PAGES = {1: "第一页最后一句没有结束", 2: "第二页接着说完。", 3: "第三页。"}

    def ingest(self):
        return IngestData(pages=dict(self.PAGES), format="pdf")

    def plan(self, locator, quote="没有结束第二页接着说完。", **extra):
        card = {"locator": locator, "quote": quote, "q": "这段在说什么？",
                "a": "跨页续写。", "kind": "claim"}
        card.update(extra)
        return {"version": 1, "deck": {"name": "P", "source_kind": "pdf"},
                "cards": [card], "skipped": []}

    def test_cross_page_quote_passes(self):
        report, stats = check_plan(self.plan("page:1-2"), self.ingest())
        self.assertEqual(report.errors + report.warnings, [])
        self.assertEqual(stats["cards"], 1)

    def test_same_quote_on_single_page_still_fails(self):
        report, _ = check_plan(self.plan("page:1"), self.ingest())
        self.assertTrue(any("逐字子串" in msg for msg in report.errors))

    def test_compile_writes_both_pages(self):
        with TemporaryDirectory() as tmp:
            report, _, out = compile_plan(self.plan("page:1-2"), self.ingest(),
                                          Path(tmp) / "deck")
            self.assertTrue(report.ok)
            payload = json.loads((out / "cards" / "01.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["cards"][0]["pages"], [1, 2])

    def test_coverage_expands_page_range(self):
        report, stats = check_plan(self.plan("page:1-2"), self.ingest(),
                                   min_coverage=0.9)
        self.assertEqual((stats["covered"], stats["groups"]), (2, 3))
        self.assertTrue(any("2/3 页被覆盖" in msg for msg in report.errors))

    def test_reversed_page_range_reports(self):
        report, _ = check_plan(self.plan("page:2-1", quote="第二页接着说完。"),
                               self.ingest())
        self.assertTrue(any("区间倒置" in msg for msg in report.errors))


class DensityTest(unittest.TestCase):
    """--density：密度带与卡型配额只提示、不拦编译。"""

    def setUp(self) -> None:
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.manifest = write_manifest(self.dir / "demo.json")
        self.ingest = load_ingest(self.manifest)

    def check(self, plan, **kwargs):
        return check_plan(plan, self.ingest, **kwargs)

    def density_warnings(self, report, needle=""):
        return [w for w in report.warnings if w.startswith("density") and needle in w]

    def test_within_band_reports_no_density_warning(self) -> None:
        # g2 30 字 + g3 20 字 = 50 字，2 张卡 = 25 字/张
        report, stats = self.check(make_plan([card_g2(), card_g3()]),
                                   density="manual", density_min=20, density_max=100)
        self.assertEqual(report.errors, [])
        self.assertEqual(self.density_warnings(report, "密于"), [])
        self.assertEqual(self.density_warnings(report, "疏于"), [])
        self.assertAlmostEqual(stats["density"]["chars_per_card"], 25.0, places=1)
        self.assertEqual(stats["density"]["cards"], 2)

    def test_manual_dense_warning_explains_exam_documents(self) -> None:
        report, _ = self.check(make_plan([card_g2(), card_g3()]), density="manual")
        [warning] = self.density_warnings(report, "密于")
        self.assertIn("题库/考点型", warning)

        report, _ = self.check(make_plan([card_g2(), card_g3()]), density="essay")
        [warning] = self.density_warnings(report, "密于")
        self.assertNotIn("题库/考点型", warning)

    def test_too_dense_warns_but_does_not_block(self) -> None:
        report, stats = self.check(make_plan([card_g2(), card_g3()]),
                                   density="essay")
        self.assertEqual(report.errors, [])
        self.assertTrue(self.density_warnings(report, "密于"))
        self.assertAlmostEqual(stats["density"]["chars_per_card"], 25.0, places=1)

    def test_too_sparse_warns(self) -> None:
        report, _ = self.check(make_plan([card_g2()]),
                               density="manual", density_min=5, density_max=10)
        self.assertTrue(self.density_warnings(report, "疏于"))

    def test_essay_profile_flags_fact_cards(self) -> None:
        report, _ = self.check(make_plan([card_g3(kind="fact")]), density="essay")
        self.assertTrue(self.density_warnings(report, "fact 卡"))

    def test_manual_profile_requires_fact_share(self) -> None:
        report, _ = self.check(make_plan([card_g2(), card_g3()]), density="manual")
        self.assertTrue(self.density_warnings(report, "合计只占"))

    def test_min_greater_than_max_is_error(self) -> None:
        report, _ = self.check(make_plan([card_g2()]),
                               density="manual", density_min=900, density_max=100)
        self.assertTrue(any("下限" in e for e in report.errors))

    def test_cli_prints_density_line(self) -> None:
        import io
        from contextlib import redirect_stdout
        plan_path = self.dir / "plan.json"
        plan_path.write_text(json.dumps(make_plan([card_g2(), card_g3()]),
                                        ensure_ascii=False), encoding="utf-8")
        out = io.StringIO()
        with redirect_stdout(out):
            code = main(["plan", "check", str(plan_path),
                         "--ingest", str(self.manifest),
                         "--density", "manual",
                         "--density-min", "20", "--density-max", "100"])
        self.assertEqual(code, 0)
        self.assertIn("密度 25 字/张（目标 20–100）", out.getvalue())


class ProcedureKindTest(unittest.TestCase):
    """procedure：流程/步骤卡，验收标准与 fact 不同（不要求数字，要求指向动作）。"""

    def setUp(self) -> None:
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.manifest = write_manifest(self.dir / "demo.json")
        self.ingest = load_ingest(self.manifest)

    def check(self, plan, **kwargs):
        return check_plan(plan, self.ingest, **kwargs)

    def test_procedure_kind_accepted(self) -> None:
        report, stats = self.check(make_plan([
            card_g2(kind="procedure", q="重试时要在请求里带上什么？",
                    a="带上同一请求号，服务端才能识别为同一次请求。")]))
        self.assertEqual(report.errors, [])
        self.assertFalse([w for w in report.warnings if ".kind" in w])
        self.assertEqual(stats["kinds"], {"procedure": 1})

    def test_procedure_question_should_point_to_action(self) -> None:
        report, _ = self.check(make_plan([
            card_g2(kind="procedure", q="幂等是什么意思？")]))
        self.assertEqual(report.errors, [])
        [warning] = [w for w in report.warnings if ".q" in w]
        self.assertIn("流程卡", warning)

    def test_procedure_needs_no_number(self) -> None:
        report, _ = self.check(make_plan([
            card_g3(kind="procedure", q="生产环境端口要怎么改？",
                    a="改配置后重启，默认 8080 只是监听值。")]))
        self.assertEqual(report.errors, [])
        self.assertEqual([w for w in report.warnings if "没有数字" in w], [])

    def test_manual_share_counts_fact_and_procedure(self) -> None:
        report, _ = self.check(make_plan([
            card_g2(kind="procedure", q="重试时要带什么？"),
            card_g3(kind="procedure", q="端口要怎么改？"),
        ]), density="manual", density_min=1, density_max=999)
        self.assertEqual([w for w in report.warnings if "合计只占" in w], [])

    def test_unknown_kind_still_error(self) -> None:
        report, _ = self.check(make_plan([card_g2(kind="workflow")]))
        self.assertTrue(any("必须是" in e for e in report.errors))


def write_plain_manifest(path: Path, lines: list[str]) -> Path:
    """不带 groups 的 txt 清单：数字写法与定位无关，只测 E2 的等价判定。"""
    units = [{"id": f"line:{i}", "line": i, "chars": len(t), "text": t}
             for i, t in enumerate(lines, 1)]
    manifest = {"format": "txt", "source": "demo.txt", "source_sha256": None,
                "unit_kind": "line", "unit_count": len(units),
                "total_chars": sum(u["chars"] for u in units),
                "units": units, "warnings": [], "encoding": "utf-8"}
    path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    return path


class NumberFormTest(unittest.TestCase):
    """E2：中文数字与阿拉伯数字按数值比对，等价即通过，但提示写法不同。"""

    LINES = [
        "试用期届满前，一方应当提前三天通知对方。",
        "员工每年享有十天带薪年假。",
        "培训费超过两百元的，需要签协议。",
        "服务期最短为三点五年。",
        "每年最多可请三十天事假。",
        "迟到超过 1.5 小时按半天计算。",
        "一班八小时，加班另计。",
    ]

    def setUp(self) -> None:
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.manifest = write_plain_manifest(self.dir / "demo.json", self.LINES)
        self.ingest = load_ingest(self.manifest)

    def card(self, line: int, answer: str, **overrides) -> dict:
        card = {"locator": f"line:{line}", "quote": self.LINES[line - 1],
                "kind": "fact", "q": "这一条怎么规定的？", "a": answer}
        card.update(overrides)
        return card

    def check(self, cards):
        return check_plan(make_plan(cards), self.ingest)

    def test_digits_answer_against_chinese_quote(self) -> None:
        report, _ = self.check([self.card(1, "提前 3 天通知对方。")])
        self.assertEqual(report.errors, [])
        self.assertTrue(any("写法与原文不同" in w for w in report.warnings))

    def test_chinese_answer_against_digits_quote(self) -> None:
        report, _ = self.check([self.card(6, "迟到超过一点五小时按半天算。")])
        self.assertEqual(report.errors, [])
        self.assertTrue(any("写法与原文不同" in w for w in report.warnings))

    def test_shi_and_liang_parse(self) -> None:
        report, _ = self.check([self.card(2, "每年 10 天年假。")])
        self.assertEqual(report.errors, [])
        report, _ = self.check([self.card(3, "超过 200 元要签协议。")])
        self.assertEqual(report.errors, [])

    def test_decimal_forms_are_equal(self) -> None:
        report, _ = self.check([self.card(4, "服务期最短 3.5 年。")])
        self.assertEqual(report.errors, [])

    def test_different_values_still_error(self) -> None:
        report, _ = self.check([self.card(1, "提前 10 天通知对方。")])
        self.assertTrue(any("答案数字 10 在 quote 里找不到" in e for e in report.errors))

        report, _ = self.check([self.card(6, "迟到超过 15 小时按半天算。")])
        self.assertTrue(any("答案数字 15 在 quote 里找不到" in e for e in report.errors))

    def test_bare_digit_sequence_not_parsed(self) -> None:
        report, _ = self.check([self.card(
            7, "一班八小时，加班另计。", kind="claim",
            q="「一二三」在这里只是一个序列，不会被当成 123 吗？")])
        self.assertEqual(report.errors, [])


def write_block_manifest(path: Path, blocks: list[str]) -> Path:
    """web 形态的清单：block:N 定位，用来模拟「另一种格式切得不一样」。"""
    units = [{"id": f"block:{i}", "locator": f"block:{i}", "kind": "paragraph",
              "chars": len(text), "text": text}
             for i, text in enumerate(blocks, 1)]
    manifest = {"format": "web", "source": "page.html", "source_sha256": None,
                "unit_kind": "block", "unit_count": len(units),
                "total_chars": sum(u["chars"] for u in units),
                "units": units, "warnings": []}
    path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    return path


class CrossFormatTest(unittest.TestCase):
    """--also：同一批 quote 换一份 ingest 重校。"""

    def setUp(self) -> None:
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.manifest = write_manifest(self.dir / "primary.json")
        self.ingest = load_ingest(self.manifest)

    def check(self, plan, **kwargs):
        return check_plan(plan, self.ingest, **kwargs)

    def test_quotes_hit_in_second_ingest(self) -> None:
        blocks = ["部署手册", "1. **幂等**：同一请求重复执行结果一致。重试时必须带同一请求号。",
                  "2. **端口**：默认监听 8080，生产需改。"]
        other = load_ingest(write_block_manifest(self.dir / "other.json", blocks))
        report, stats = self.check(make_plan([card_g2(), card_g3()]), also=[other])
        self.assertEqual(report.errors, [])
        self.assertEqual([w for w in report.warnings if w.startswith("also")], [])
        self.assertEqual(stats["also"][0]["hit"], 2)
        self.assertEqual(stats["also"][0]["miss"], 0)

    def test_missing_quote_warns(self) -> None:
        other = load_ingest(write_block_manifest(
            self.dir / "other.json", ["部署手册", "1. **幂等**：结果一致。", "2. **端口**：默认 8080。"]))
        report, stats = self.check(make_plan([card_g2()]), also=[other])
        self.assertTrue(any("找不到逐字引用" in w for w in report.warnings))
        self.assertEqual(stats["also"][0]["miss"], 1)

    def test_split_across_units_is_reported(self) -> None:
        # 第二份把一句拆成两块，整段拼接后仍能命中
        blocks = ["部署手册", "1. **幂等**：同一请求重复执行结果一致。",
                  "重试时必须带同一请求号。", "2. **端口**：默认监听 8080，生产需改。"]
        other = load_ingest(write_block_manifest(self.dir / "other.json", blocks))
        report, stats = self.check(make_plan([card_g2()]), also=[other])
        self.assertEqual(stats["also"][0]["hit"], 1)
        self.assertEqual(stats["also"][0]["split"], 1)
        self.assertTrue(any("跨单元拼接" in w for w in report.warnings))

    def test_same_format_warns(self) -> None:
        report, _ = self.check(make_plan([card_g2()]), also=[self.ingest])
        self.assertTrue(any("同为 txt" in w for w in report.warnings))


def write_epub_manifest(path: Path, chapters: list[list[str]]) -> Path:
    """epub 形态的清单：chapter:C/p:M 定位，用于小说剧透检查。"""
    units = []
    for chapter, paragraphs in enumerate(chapters, 1):
        for para, text in enumerate(paragraphs, 1):
            units.append({"id": f"chapter:{chapter}/p:{para}",
                          "locator": f"chapter:{chapter}/p:{para}",
                          "kind": "paragraph", "chars": len(text), "text": text})
    manifest = {"format": "epub", "source": "book.epub", "source_sha256": None,
                "unit_kind": "paragraph", "unit_count": len(units),
                "total_chars": sum(u["chars"] for u in units),
                "chapter_count": len(chapters), "units": units, "warnings": []}
    path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    return path


class SpoilerTest(unittest.TestCase):
    """novel profile：复制后文句子 / 后文名字 / 声明的实体。"""

    def setUp(self) -> None:
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.manifest = write_epub_manifest(self.dir / "book.json", [
            ["第一章。天氣很好。", "我遇見了阿明，他笑了三聲。"],
            ["故事繼續前進。"],
            ["林小姐走進來，全場安靜下來。Linda 也到了。", "結束。"],
        ])
        self.ingest = load_ingest(self.manifest)

    def card(self, locator: str, q: str, a: str, quote: str) -> dict:
        return {"kind": "claim", "locator": locator, "quote": quote,
                "q": q, "a": a, "type": "qa"}

    def plan(self, cards, entities=None) -> dict:
        plan = {"version": 1, "deck": {"name": "小說", "source_kind": "epub"},
                "cards": cards, "skipped": []}
        if entities is not None:
            plan["entities"] = entities
        return plan

    def test_copied_later_sentence_warns(self) -> None:
        card = self.card("chapter:1/p:1", "現場會怎樣？", "全場安靜下來。", "第一章。天氣很好。")
        report, stats = check_plan(self.plan([card]), self.ingest, profile="novel")
        self.assertTrue(any("复制了后文才出现的句子" in w and "全場安靜" in w
                            for w in report.warnings))
        self.assertEqual(stats["spoiler"]["windows"], 1)

    def test_later_latin_name_warns(self) -> None:
        card = self.card("chapter:1/p:1", "Linda 是誰？", "不知道。", "第一章。天氣很好。")
        report, stats = check_plan(self.plan([card]), self.ingest, profile="novel")
        self.assertTrue(any("后文才出场的名字「linda」" in w for w in report.warnings))
        self.assertEqual(stats["spoiler"]["names"], 1)

    def test_early_paraphrase_no_warning(self) -> None:
        card = self.card("chapter:1/p:2", "阿明是誰？", "我在第一章遇見的人。", "我遇見了阿明，他笑了三聲。")
        report, stats = check_plan(self.plan([card]), self.ingest, profile="novel")
        self.assertEqual(stats["spoiler"]["windows"], 0)
        self.assertEqual(stats["spoiler"]["names"], 0)

    def test_declared_entity_before_appearance_is_error(self) -> None:
        card = self.card("chapter:1/p:1", "林小姐為什麼生氣？", "她走了。", "第一章。天氣很好。")
        plan = self.plan([card], entities=[{"name": "林小姐", "locator": "chapter:3/p:1"}])
        report, _ = check_plan(plan, self.ingest, profile="novel")
        self.assertTrue(any("剧透：实体「林小姐」" in e for e in report.errors))

    def test_declared_entity_after_appearance_ok(self) -> None:
        card = self.card("chapter:3/p:1", "林小姐為什麼走進來？", "她讓全場安靜下來。",
                         "林小姐走進來，全場安靜下來。")
        plan = self.plan([card], entities=[{"name": "林小姐", "locator": "chapter:3/p:1"}])
        report, _ = check_plan(plan, self.ingest, profile="novel")
        self.assertEqual([e for e in report.errors if "剧透" in e], [])

    def test_bad_entity_locator_errors(self) -> None:
        plan = self.plan([], entities=[{"name": "林小姐", "locator": "line:3"}])
        report, _ = check_plan(plan, self.ingest, profile="novel")
        self.assertTrue(any("chapter:C/p:M" in e for e in report.errors))

    def test_manual_profile_skips_check(self) -> None:
        card = self.card("chapter:1/p:1", "Linda 是誰？", "不知道。", "第一章。天氣很好。")
        _, stats = check_plan(self.plan([card]), self.ingest, profile="manual")
        self.assertNotIn("spoiler", stats)


class IncrementalTest(unittest.TestCase):
    """plan compile --incremental：保留旧卡、按 key 替换、按 retired 下架。"""

    def setUp(self) -> None:
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.ingest = load_ingest(write_block_manifest(self.dir / "ingest.json", [
            "部署手册：本手册说明上线流程。",
            "1. 幂等：同一请求重复执行结果一致。",
            "重试时必须带同一请求号。",
            "2. 端口：默认监听 8080，生产需改。",
        ]))
        self.deck = self.dir / "deck"

    def card(self, locator: str, quote: str, q: str, a: str, key: str) -> dict:
        return {"kind": "claim", "locator": locator, "quote": quote,
                "q": q, "a": a, "type": "qa", "key": key}

    def first(self) -> None:
        plan = {"version": 1, "deck": {"name": "演示", "source_kind": "web"},
                "cards": [self.card("block:2", "同一请求重复执行结果一致", "幂等是什么意思？",
                                    "结果一致，无需额外处理", "aaaaaaaaaaaa"),
                          self.card("block:4", "默认监听 8080，生产需改", "端口默认是多少？",
                                    "8080，生产要改", "bbbbbbbbbbbb")]}
        report, _, out = compile_plan(plan, self.ingest, self.deck)
        self.assertTrue(report.ok, report.errors)
        self.assertIsNotNone(out)

    def test_merge_keeps_replaces_and_retires(self) -> None:
        self.first()
        plan = {"version": 1, "deck": {"name": "演示", "source_kind": "web"},
                "cards": [self.card("block:2", "同一请求重复执行结果一致", "幂等是什么意思？",
                                    "结果一致（改过措辞）", "aaaaaaaaaaaa"),
                          self.card("block:3", "重试时必须带同一请求号", "重试要注意什么？",
                                    "带同一请求号", "cccccccccccc")],
                "retired": ["bbbbbbbbbbbb"]}
        report, stats, out = compile_plan(plan, self.ingest, self.deck, incremental=True)
        self.assertTrue(report.ok, report.errors)
        self.assertIsNotNone(out)

        spec = load_spec(self.deck)
        cards = [card for section in spec.sections for card in section["cards"]]
        self.assertEqual(sorted(card["key"] for card in cards),
                         ["aaaaaaaaaaaa", "cccccccccccc"])
        self.assertIn("改过措辞", [c for c in cards if c["key"] == "aaaaaaaaaaaa"][0]["a"])
        self.assertEqual(stats["incremental"]["kept"], 0)
        self.assertEqual(stats["incremental"]["new"], 1)
        self.assertEqual(stats["incremental"]["retired"], 1)

    def test_keeps_untouched_old_cards(self) -> None:
        self.first()
        plan = {"version": 1, "deck": {"name": "演示", "source_kind": "web"},
                "cards": [self.card("block:3", "重试时必须带同一请求号", "重试要注意什么？",
                                    "带同一请求号", "cccccccccccc")]}
        report, stats, _ = compile_plan(plan, self.ingest, self.deck, incremental=True)
        self.assertTrue(report.ok, report.errors)
        self.assertEqual(stats["incremental"]["kept"], 2)
        self.assertEqual(stats["incremental"]["new"], 1)

    def test_derives_keys_when_missing(self) -> None:
        self.first()
        # block:3 之前没发布过，现算的 key 只会新增一张
        plan = {"version": 1, "deck": {"name": "演示", "source_kind": "web"},
                "cards": [{"kind": "claim", "locator": "block:3",
                           "quote": "重试时必须带同一请求号", "q": "重试注意什么？",
                           "a": "带同一请求号", "type": "qa"}]}
        report, stats, out = compile_plan(plan, self.ingest, self.deck, incremental=True)
        self.assertTrue(report.ok, report.errors)
        self.assertEqual(stats["incremental"]["new"], 1)
        cards = [c for section in load_spec(self.deck).sections for c in section["cards"]]
        self.assertTrue(all(len(c["key"]) == 12 for c in cards))

    def test_requires_existing_deck(self) -> None:
        plan = {"version": 1, "deck": {"name": "演示", "source_kind": "web"},
                "cards": [self.card("block:3", "重试时必须带同一请求号", "重试注意什么？",
                                    "带同一请求号", "cccccccccccc")]}
        with self.assertRaises(CardError):
            compile_plan(plan, self.ingest, self.dir / "missing", incremental=True)

    def test_retired_and_card_same_key_is_error(self) -> None:
        plan = {"version": 1, "deck": {"name": "演示", "source_kind": "web"},
                "cards": [self.card("block:3", "重试时必须带同一请求号", "重试注意什么？",
                                    "带同一请求号", "aaaaaaaaaaaa")],
                "retired": ["aaaaaaaaaaaa"]}
        report, _ = check_plan(plan, self.ingest)
        self.assertTrue(any("既是退场又要出卡" in e for e in report.errors))

    def test_unknown_retired_key_warns(self) -> None:
        self.first()
        plan = {"version": 1, "deck": {"name": "演示", "source_kind": "web"},
                "cards": [self.card("block:3", "重试时必须带同一请求号", "重试注意什么？",
                                    "带同一请求号", "cccccccccccc")],
                "retired": ["dddddddddddd"]}
        report, _, _ = compile_plan(plan, self.ingest, self.deck, incremental=True)
        self.assertTrue(any("不在现有牌组里" in w for w in report.warnings))
