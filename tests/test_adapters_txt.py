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


if __name__ == "__main__":
    unittest.main()
