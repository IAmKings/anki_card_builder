"""可卡性预检：PDF 必须按行算结构指标，页级只做版面提示。"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from ankicards.precheck import analyze, format_report

ROOT = Path(__file__).resolve().parents[1]


def pdf_manifest(pages: list[str]) -> dict:
    units = [{"id": f"page:{i}", "locator": f"page:{i}", "chars": len(t),
              "text": t} for i, t in enumerate(pages, 1)]
    return {"format": "pdf", "source": "demo.pdf", "unit_kind": "page",
            "unit_count": len(units), "units": units}


def txt_manifest(lines: list[str]) -> dict:
    units = [{"id": f"line:{i}", "line": i, "chars": len(t), "text": t}
             for i, t in enumerate(lines, 1)]
    return {"format": "txt", "source": "demo.txt", "unit_kind": "line",
            "unit_count": len(units), "units": units}


class PrecheckTest(unittest.TestCase):
    def test_pdf_is_measured_by_lines_not_pages(self) -> None:
        page = "1. 甲：一\n2. 乙：二\n3. 丙：三\n4. 丁：四"
        result = analyze(pdf_manifest([page, page]))
        s = result["structural"]
        self.assertEqual(s["units"], 8)  # 2 页 × 4 行
        self.assertAlmostEqual(s["numbering_ratio"], 1.0)
        self.assertEqual(result["layout"]["pages"], 2)

    def test_txt_units_are_lines(self) -> None:
        result = analyze(txt_manifest(["1. 甲：一", "普通一行"]))
        self.assertAlmostEqual(result["structural"]["numbering_ratio"], 0.5)

    def test_low_numbering_forbids_adapter(self) -> None:
        result = analyze(txt_manifest(["散文一句", "另一句"]))
        tips = " ".join(result["advice"])
        self.assertIn("禁止 *-points", tips)
        self.assertNotIn("可尝试 *-points", tips)

    def test_high_numbering_suggests_adapter(self) -> None:
        result = analyze(txt_manifest(["1. 甲：一", "2. 乙：二", "3. 丙：三"]))
        self.assertIn("可尝试 *-points", " ".join(result["advice"]))

    def test_no_digits_means_no_fact_cards(self) -> None:
        result = analyze(txt_manifest(["全部是文字", "没有任何数字"]))
        self.assertIn("不出 fact", " ".join(result["advice"]))

    def test_digit_heavy_suggests_fact(self) -> None:
        result = analyze(txt_manifest(["1. 上限 8 小时", "2. 月薪 3000 元"]))
        self.assertIn("fact 可为主力", " ".join(result["advice"]))

    def test_long_pdf_pages_warn_layout(self) -> None:
        result = analyze(pdf_manifest(["长" * 400]))
        self.assertAlmostEqual(result["layout"]["long_page_ratio"], 1.0)
        self.assertIn("版面密度高", " ".join(result["advice"]))

    def test_report_has_structural_then_layout(self) -> None:
        text = format_report(analyze(pdf_manifest(["1. 甲：一\n" + "字" * 400])))
        self.assertIn("结构单元", text)
        self.assertIn("版面：", text)
        self.assertLess(text.index("结构单元"), text.index("版面："))

    def test_cli_prints_report_and_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manifest = Path(tmp) / "ingest.json"
            manifest.write_text(json.dumps(txt_manifest(["1. 甲：一", "2. 乙：二"]),
                                           ensure_ascii=False), encoding="utf-8")
            out = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "precheck.py"),
                 "--ingest", str(manifest)],
                capture_output=True, text=True)
            self.assertEqual(out.returncode, 0, out.stderr)
            self.assertIn("编号点", out.stdout)

            out = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "precheck.py"),
                 "--ingest", str(manifest), "--json"],
                capture_output=True, text=True)
            self.assertEqual(out.returncode, 0, out.stderr)
            payload = json.loads(out.stdout)
            self.assertAlmostEqual(payload["structural"]["numbering_ratio"], 1.0)


if __name__ == "__main__":
    unittest.main()
