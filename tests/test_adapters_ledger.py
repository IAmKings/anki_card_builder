"""适配器账本：未出卡理由、内容规则命中、import-report.json 与 --strict。"""

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from ankicards.adapters import build_report, from_txt_points, write_deck
from ankicards.cli import main

SAMPLE = """# 部署手册

1. **环境准备**：安装依赖

  - 配置 PATH
  - 安装工具

1. **启动服务**：监听端口 8080；

生产环境需覆盖配置并开启 TLS。

1. **日志位置**：见第 4 节。

1. **幂等**：同一操作执行多次与执行一次结果一致。
"""


def run_cli(args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(args)
    return code, out.getvalue() + err.getvalue()


class TxtLedgerTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.source = self.tmp / "demo.txt"
        self.source.write_text(SAMPLE, encoding="utf-8")
        self.deck = from_txt_points(self.source)

    def tearDown(self):
        self._tmp.cleanup()

    def test_cards_are_still_extracted(self):
        self.assertEqual(self.deck.card_count, 4)
        self.assertEqual(list(self.deck.sections), ["部署手册"])

    def test_every_non_card_line_has_a_reason(self):
        counts = self.deck.count_skipped()
        self.assertEqual(counts["heading"], 1)
        self.assertEqual(counts["continuation"], 3)
        self.assertEqual(counts["blank"], 6)
        self.assertEqual(len(self.deck.skipped), 10)

    def test_known_failures_are_flagged(self):
        counts = self.deck.count_findings()
        self.assertEqual(counts.get("Q1"), 1)  # 环境准备：答案过短
        self.assertEqual(counts.get("Q2"), 1)  # 启动服务：答案停在分号
        self.assertEqual(counts.get("Q3"), 1)  # 日志位置：只有交叉引用

    def test_findings_carry_locator_and_level(self):
        by_rule = {item["rule"]: item for item in self.deck.findings}
        self.assertEqual(by_rule["Q2"]["locator"], "line:8")
        self.assertEqual(by_rule["Q2"]["level"], "error")
        self.assertEqual(by_rule["Q3"]["locator"], "line:12")

    def test_write_deck_emits_report(self):
        out = write_deck(self.deck, self.tmp / "deck")
        report = json.loads((out / "import-report.json").read_text(encoding="utf-8"))
        self.assertEqual(report["cards"], 4)
        self.assertEqual(report["source_kind"], "txt")
        self.assertEqual(report["skipped_by_reason"]["continuation"], 3)
        self.assertEqual(report["findings_by_level"]["error"], 3)
        self.assertEqual(report["findings_by_rule"], {"Q1": 1, "Q2": 1, "Q3": 1})
        # 账本是附加文件，不改变牌组自身的契约
        self.assertTrue((out / "deck.json").exists())
        self.assertEqual(len(list((out / "cards").glob("*.json"))), 1)

    def test_build_report_matches_deck(self):
        report = build_report(self.deck)
        self.assertEqual(report["skipped_total"], 10)
        self.assertEqual(report["findings_total"], 3)
        self.assertEqual(len(report["skipped"]), 10)
        self.assertEqual(len(report["findings"]), 3)

    def test_default_import_exits_zero_and_prints_summary(self):
        out = self.tmp / "deck"
        code, output = run_cli(["import", str(self.source), "--adapter", "txt-points",
                                "--out", str(out)])
        self.assertEqual(code, 0, output)
        self.assertIn("已导出到", output)
        self.assertIn("内容检查：3 个可疑项", output)
        self.assertIn("未出卡 10 处", output)
        self.assertTrue((out / "import-report.json").exists())

    def test_strict_refuses_to_write(self):
        out = self.tmp / "deck"
        code, output = run_cli(["import", str(self.source), "--adapter", "txt-points",
                                "--out", str(out), "--strict"])
        self.assertEqual(code, 1, output)
        self.assertIn("--strict", output)
        self.assertFalse((out / "cards").exists())
        self.assertFalse((out / "deck.json").exists())

    def test_clean_source_has_no_findings(self):
        path = self.tmp / "clean.txt"
        path.write_text("1. **幂等**：同一操作执行多次与执行一次结果一致。\n",
                        encoding="utf-8")
        deck = from_txt_points(path)
        self.assertEqual(deck.findings, [])
        self.assertEqual(deck.count_skipped(), {})
        code, output = run_cli(["import", str(path), "--adapter", "txt-points",
                                "--out", str(self.tmp / "clean"), "--strict"])
        self.assertEqual(code, 0, output)
        self.assertNotIn("内容检查", output)


if __name__ == "__main__":
    unittest.main()
