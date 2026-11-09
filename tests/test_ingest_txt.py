"""TXT 文本摄取：物理行定位、编码、空行与限制。

定位语法：
- line:N  按 splitlines() 的物理行计数（1 基；空行也计数）
"""

import contextlib
import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from ankicards import ingest as ingest_mod
from ankicards.cli import main


def run_cli(args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(args)
    return code, out.getvalue() + err.getvalue()


class IngestTxtTest(unittest.TestCase):
    def test_lines_and_empty_lines_have_locators(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "a.txt"
            path.write_text("第一行\n\n第三行\n", encoding="utf-8")
            result = ingest_mod.ingest_txt(
                path, out=Path(tmp) / "out.json", repo_root=Path(tmp))
            manifest = result.manifest
            self.assertEqual(manifest["format"], "txt")
            self.assertEqual(manifest["unit_kind"], "line")
            self.assertEqual(manifest["source"], "a.txt")
            self.assertEqual([u["id"] for u in manifest["units"]],
                             ["line:1", "line:2", "line:3"])
            self.assertEqual([u["line"] for u in manifest["units"]], [1, 2, 3])
            self.assertEqual(manifest["units"][1]["text"], "")
            self.assertEqual(manifest["empty_lines"], [2])
            self.assertEqual(manifest["total_chars"], 6)
            self.assertEqual(manifest["source_sha256"],
                             hashlib.sha256(path.read_bytes()).hexdigest())

    def test_utf8_bom_default_is_stripped(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bom.txt"
            path.write_bytes("\ufeff一\n二\n".encode("utf-8"))
            manifest = ingest_mod.ingest_txt(
                path, out=Path(tmp) / "out.json", repo_root=Path(tmp)).manifest
            self.assertEqual(manifest["encoding"], "utf-8-sig")
            self.assertEqual(manifest["units"][0]["text"], "一")
            self.assertNotIn("\ufeff", manifest["units"][0]["text"])

    def test_gb18030_encoding(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "gb.txt"
            path.write_bytes("中文\n第二行\n".encode("gb18030"))
            manifest = ingest_mod.ingest_txt(
                path, out=Path(tmp) / "out.json", encoding="gb18030",
                repo_root=Path(tmp)).manifest
            self.assertEqual(manifest["encoding"], "gb18030")
            self.assertEqual(manifest["units"][0]["text"], "中文")
            self.assertEqual(manifest["units"][1]["text"], "第二行")

    def test_unknown_encoding_is_usage_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "a.txt"
            path.write_text("一\n", encoding="utf-8")
            with self.assertRaises(ingest_mod.IngestError) as ctx:
                ingest_mod.ingest_txt(path, out=Path(tmp) / "out.json",
                                      encoding="no-such-codec")
            self.assertEqual(ctx.exception.code, 2)
            self.assertIn("编码", str(ctx.exception))

    def test_invalid_bytes_is_usage_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.txt"
            path.write_bytes(b"\xff\xfe\x00")
            with self.assertRaises(ingest_mod.IngestError) as ctx:
                ingest_mod.ingest_txt(path, out=Path(tmp) / "out.json",
                                      repo_root=Path(tmp))
            self.assertEqual(ctx.exception.code, 2)
            self.assertIn("解码", str(ctx.exception))

    def test_empty_and_whitespace_only_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            empty = Path(tmp) / "empty.txt"
            empty.write_text("", encoding="utf-8")
            spaces = Path(tmp) / "spaces.txt"
            spaces.write_text("\n   \n\n", encoding="utf-8")
            for path in (empty, spaces):
                with self.assertRaises(ingest_mod.IngestError) as ctx:
                    ingest_mod.ingest_txt(path, out=Path(tmp) / "out.json",
                                          repo_root=Path(tmp))
                self.assertEqual(ctx.exception.code, 2)
                self.assertIn("没有可提取文本", str(ctx.exception))

    def test_max_lines(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "a.txt"
            path.write_text("一\n二\n三\n", encoding="utf-8")
            with self.assertRaises(ingest_mod.IngestError) as ctx:
                ingest_mod.ingest_txt(path, out=Path(tmp) / "out.json",
                                      max_lines=2, repo_root=Path(tmp))
            self.assertEqual(ctx.exception.code, 2)
            self.assertIn("上限", str(ctx.exception))

    def test_size_limit_is_checked_before_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "a.txt"
            path.write_text("一\n", encoding="utf-8")
            with mock.patch.object(ingest_mod, "MAX_TXT_BYTES", 1):
                with self.assertRaises(ingest_mod.IngestError) as ctx:
                    ingest_mod.ingest_txt(path, out=Path(tmp) / "out.json",
                                          repo_root=Path(tmp))
            self.assertEqual(ctx.exception.code, 2)
            self.assertIn("上限", str(ctx.exception))

    def test_output_is_deterministic_and_relative(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "a.txt"
            path.write_text("一\n二\n", encoding="utf-8")
            one = Path(tmp) / "1.json"
            two = Path(tmp) / "2.json"
            ingest_mod.ingest_txt(path, out=one, repo_root=Path(tmp))
            ingest_mod.ingest_txt(path, out=two, repo_root=Path(tmp))
            self.assertEqual(one.read_bytes(), two.read_bytes())
            text = one.read_text(encoding="utf-8")
            self.assertEqual(json.loads(text)["source"], "a.txt")
            self.assertNotIn(str(path), text)

    def test_empty_ratio_warns_but_does_not_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sparse.txt"
            path.write_text("一\n\n\n\n\n", encoding="utf-8")
            manifest = ingest_mod.ingest_txt(
                path, out=Path(tmp) / "out.json", repo_root=Path(tmp)).manifest
            self.assertEqual(manifest["empty_lines"], [2, 3, 4, 5])
            self.assertTrue(any("空行" in w for w in manifest["warnings"]))

    def test_dispatch_by_extension(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "a.txt"
            path.write_text("一\n", encoding="utf-8")
            manifest = ingest_mod.ingest(
                path, out=Path(tmp) / "out.json", repo_root=Path(tmp)).manifest
            self.assertEqual(manifest["format"], "txt")

    def test_load_ingest_exposes_lines(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "a.txt"
            path.write_text("一\n\n三\n", encoding="utf-8")
            result = ingest_mod.ingest_txt(
                path, out=Path(tmp) / "out.json", repo_root=Path(tmp))
            data = ingest_mod.load_ingest(result.out_path)
            self.assertEqual(data.format, "txt")
            self.assertEqual(data.pages, {})
            self.assertEqual(data.locators["line:2"], "")
            self.assertEqual(data.locators["line:3"], "三")
            self.assertEqual(data.source_sha256, ingest_mod.file_sha256(path))

    def test_cli_ingest_txt(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "a.txt"
            path.write_text("一\n二\n", encoding="utf-8")
            out = Path(tmp) / "out.json"
            code, output = run_cli(["ingest", str(path), "--out", str(out)])
            self.assertEqual(code, 0, output)
            self.assertIn("2 行", output)
            self.assertEqual(json.loads(out.read_text(encoding="utf-8"))["format"], "txt")

    def test_non_txt_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "a.text"
            path.write_text("一\n", encoding="utf-8")
            with self.assertRaises(ingest_mod.IngestError) as ctx:
                ingest_mod.ingest_txt(path, out=Path(tmp) / "out.json")
            self.assertEqual(ctx.exception.code, 2)
            self.assertIn(".txt", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
