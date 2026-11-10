"""ingest groups：续行/子项并入同一段，span 覆盖全部非空单元，区间定位可被闸门使用。"""

import json
import tempfile
import unittest
from pathlib import Path

from ankicards import ingest as ingest_mod
from ankicards.ingest import IngestError

DEMO = ("部署手册\n"
        "1. **环境准备**：安装 JDK 17，配置 JAVA_HOME。\n"
        "   - Windows：使用安装包\n"
        "   - macOS：brew install openjdk@17\n"
        "\n"
        "2. **启动服务**：执行 `java -jar app.jar`，默认端口 8080；\n"
        "   生产环境需覆盖配置并开启 TLS。\n")


def ingest_txt(tmp: Path, text: str = DEMO):
    path = tmp / "a.txt"
    path.write_text(text, encoding="utf-8")
    result = ingest_mod.ingest_txt(path, out=tmp / "ing.json", repo_root=tmp)
    return result, path


class TxtGroupsTest(unittest.TestCase):
    def test_continuation_and_subitems_join_the_point(self):
        with tempfile.TemporaryDirectory() as tmp:
            result, _ = ingest_txt(Path(tmp))
            groups = result.manifest["groups"]
            self.assertEqual([g["kind"] for g in groups], ["prose", "point", "point"])
            self.assertEqual(groups[1]["locator"], "line:2-4")
            self.assertEqual(groups[1]["unit_locators"],
                             ["line:2", "line:3", "line:4"])
            self.assertEqual(groups[2]["locator"], "line:6-7")

    def test_every_non_blank_line_is_grouped(self):
        with tempfile.TemporaryDirectory() as tmp:
            result, _ = ingest_txt(Path(tmp))
            manifest = result.manifest
            covered = {locator for group in manifest["groups"]
                       for locator in group["unit_locators"]}
            non_blank = {unit["id"] for unit in manifest["units"]
                         if unit["text"].strip()}
            self.assertEqual(covered, non_blank)

    def test_blank_line_closes_group(self):
        with tempfile.TemporaryDirectory() as tmp:
            result, _ = ingest_txt(
                Path(tmp), "1. **甲**：一\n\n2. **乙**：二\n")
            groups = result.manifest["groups"]
            self.assertEqual([g["locator"] for g in groups], ["line:1", "line:3"])

    def test_unindented_text_after_sentence_start_new_prose_group(self):
        with tempfile.TemporaryDirectory() as tmp:
            result, _ = ingest_txt(
                Path(tmp), "1. **甲**：一句话。\n另一段独立说明。\n")
            groups = result.manifest["groups"]
            self.assertEqual([g["kind"] for g in groups], ["point", "prose"])

    def test_previous_line_ending_with_comma_joins(self):
        with tempfile.TemporaryDirectory() as tmp:
            result, _ = ingest_txt(
                Path(tmp), "1. **甲**：前半句，\n后半句。\n")
            groups = result.manifest["groups"]
            self.assertEqual(len(groups), 1)
            self.assertEqual(groups[0]["locator"], "line:1-2")

    def test_load_ingest_registers_range_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            result, _ = ingest_txt(Path(tmp))
            data = ingest_mod.load_ingest(result.out_path)
            text = data.locators["line:2-4"]
            self.assertIn("JDK 17", text)
            self.assertIn("macOS", text)
            self.assertIn("line:6-7", data.locators)

    def test_manifest_without_groups_still_loads(self):
        """旧 ingest 产物没有 groups，必须继续可用（P2 之前的行为）。"""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "old.json"
            path.write_text(json.dumps({
                "format": "txt", "source_sha256": None,
                "units": [{"id": "line:1", "line": 1, "chars": 2, "text": "一"}],
            }, ensure_ascii=False), encoding="utf-8")
            data = ingest_mod.load_ingest(path)
            self.assertEqual(data.locators, {"line:1": "一"})

    def test_group_with_missing_unit_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.json"
            path.write_text(json.dumps({
                "format": "txt",
                "units": [{"id": "line:1", "line": 1, "chars": 2, "text": "一"}],
                "groups": [{"id": "g1", "kind": "point", "locator": "line:1-2",
                            "unit_locators": ["line:1", "line:9"], "span": ["line:1", "line:9"]}],
            }, ensure_ascii=False), encoding="utf-8")
            with self.assertRaises(IngestError) as ctx:
                ingest_mod.load_ingest(path)
            self.assertIn("line:9", str(ctx.exception))


class WebGroupsTest(unittest.TestCase):
    def test_list_items_join_numbered_paragraph(self):
        html = ("<html><body><h2>部署</h2>"
                "<p>1. **启动**：执行命令</p>"
                "<ul><li>先改配置</li><li>再重启</li></ul>"
                "</body></html>")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "a.html"
            path.write_text(html, encoding="utf-8")
            result = ingest_mod.ingest_html(path, out=Path(tmp) / "ing.json",
                                            repo_root=Path(tmp))
            groups = result.manifest["groups"]
            self.assertEqual(groups[0]["kind"], "heading")
            point = groups[1]
            self.assertEqual(point["kind"], "point")
            self.assertEqual(len(point["unit_locators"]), 3)
            self.assertTrue(point["locator"].endswith("-4"))


if __name__ == "__main__":
    unittest.main()
