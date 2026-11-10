"""txt-points 适配器：标题分段 + 编号点，source 必须与 ingest 的 line:N 对齐。"""

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from ankicards import ingest as ingest_mod
from ankicards.adapters import from_txt_points
from ankicards.cli import main
from ankicards.errors import CardError


def run_cli(args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(args)
    return code, out.getvalue() + err.getvalue()


class TxtPointsAdapterTest(unittest.TestCase):
    def test_headings_and_points_use_physical_line_numbers(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "a.txt"
            path.write_text(
                "# 网络\n\n1. **TCP**：可靠的传输层协议\n2. **UDP**：无连接的传输层协议\n",
                encoding="utf-8")
            deck = from_txt_points(path)
            self.assertEqual(deck.source_kind, "txt")
            self.assertEqual(list(deck.sections), ["网络"])
            cards = deck.sections["网络"]
            self.assertEqual([c["source"] for c in cards], ["line:3", "line:4"])
            self.assertEqual(cards[0]["a"], "可靠的传输层协议")
            self.assertIn("source:txt", cards[0]["tags"])

    def test_chinese_heading_without_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "a.txt"
            path.write_text("一、基础\n1. **MTU**：最大传输单元\n", encoding="utf-8")
            deck = from_txt_points(path)
            self.assertEqual(list(deck.sections), ["基础"])

    def test_plain_numbered_point(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "a.txt"
            path.write_text("1. TCP：可靠传输\n", encoding="utf-8")
            deck = from_txt_points(path)
            self.assertEqual(deck.sections["默认"][0]["a"], "可靠传输")

    def test_blank_lines_keep_line_numbers(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "a.txt"
            path.write_text("\n\n1. **X**：Y\n", encoding="utf-8")
            deck = from_txt_points(path)
            self.assertEqual(deck.sections["默认"][0]["source"], "line:3")

    def test_no_points_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "a.txt"
            path.write_text("# 只有标题\n\n随便一段文字\n", encoding="utf-8")
            with self.assertRaises(CardError) as ctx:
                from_txt_points(path)
            self.assertIn("没有解析出", str(ctx.exception))

    def test_directory_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(CardError) as ctx:
                from_txt_points(Path(tmp))
            self.assertIn("单个 .txt", str(ctx.exception))

    def test_non_txt_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "a.md"
            path.write_text("1. **X**：Y\n", encoding="utf-8")
            with self.assertRaises(CardError) as ctx:
                from_txt_points(path)
            self.assertIn(".txt", str(ctx.exception))

    def test_invalid_utf8_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "a.txt"
            path.write_bytes(b"\xff\xfe")
            with self.assertRaises(CardError) as ctx:
                from_txt_points(path)
            self.assertIn("UTF-8", str(ctx.exception))


class TxtPointsCliTest(unittest.TestCase):
    def test_import_and_check_with_ingest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            txt = root / "a.txt"
            txt.write_text("# 网络\n1. **TCP**：可靠\n", encoding="utf-8")
            deck = root / "deck"
            code, output = run_cli(["import", str(txt), "--adapter", "txt-points",
                                    "--out", str(deck)])
            self.assertEqual(code, 0, output)
            self.assertEqual(json.loads((deck / "deck.json").read_text(encoding="utf-8"))
                             ["source_kind"], "txt")
            manifest = ingest_mod.ingest_txt(
                txt, out=root / "ing.json", repo_root=root).out_path
            code, output = run_cli(["check", str(deck), "--txt", str(txt),
                                    "--ingest", str(manifest)])
            self.assertEqual(code, 0, output)

    def test_ingest_groups_merge_continuation_and_subitems(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            txt = root / "a.txt"
            txt.write_text(
                "部署手册\n"
                "1. **环境准备**：安装 JDK 17，配置 JAVA_HOME。\n"
                "   - Windows：使用安装包\n"
                "   - macOS：brew install openjdk@17\n"
                "\n"
                "2. **启动服务**：执行 `java -jar app.jar`，默认端口 8080；\n"
                "   生产环境需覆盖配置并开启 TLS。\n",
                encoding="utf-8")
            manifest = ingest_mod.ingest_txt(
                txt, out=root / "ing.json", repo_root=root).out_path
            deck_dir = root / "deck"
            code, output = run_cli(["import", str(txt), "--adapter", "txt-points",
                                    "--ingest", str(manifest), "--out", str(deck_dir),
                                    "--name", "演示"])
            self.assertEqual(code, 0, output)
            cards = json.loads(
                (deck_dir / "cards" / "01.json").read_text(encoding="utf-8"))["cards"]
            by_question = {card["q"]: card for card in cards}

            start = by_question["什么是启动服务？"]
            self.assertEqual(start["source"], "line:6-7")
            self.assertIn("生产环境需覆盖配置并开启 TLS。", start["a"])

            env = by_question["什么是环境准备？"]
            self.assertEqual(env["source"], "line:2-4")
            self.assertIn("Windows", env["a"])
            self.assertIn("macOS", env["a"])

    def test_ingest_format_mismatch_is_exit_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            txt = root / "a.txt"
            txt.write_text("1. **X**：Y\n", encoding="utf-8")
            manifest = root / "web.json"
            manifest.write_text(json.dumps({
                "format": "web",
                "units": [{"id": "block:1", "locator": "block:1",
                           "kind": "paragraph", "text": "1. **X**：Y"}],
                "groups": [{"id": "g1", "kind": "point", "locator": "block:1",
                            "unit_locators": ["block:1"]}],
            }, ensure_ascii=False), encoding="utf-8")
            code, output = run_cli(["import", str(txt), "--adapter", "txt-points",
                                    "--ingest", str(manifest), "--out", str(root / "deck")])
            self.assertEqual(code, 2, output)
            self.assertIn("format", output)


if __name__ == "__main__":
    unittest.main()
