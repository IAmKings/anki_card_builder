"""web-points 适配器：本地 HTML / web ingest manifest → 标题 + 编号点。"""

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from ankicards import ingest as ingest_mod
from ankicards.adapters import from_web_points
from ankicards.cli import main

HTML = """
<html><body>
<h1>网络基础</h1>
<p>1. **TCP**：面向连接、可靠传输</p>
<ul><li>2. **UDP**：无连接、不保证可靠</li></ul>
<h2>应用层</h2>
<p>3. **HTTP**：无状态的应用层协议</p>
<table><tr><td>端口</td><td>说明</td></tr>
<tr><td>80</td><td>HTTP</td></tr></table>
</body></html>
"""


def run_cli(args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(args)
    return code, out.getvalue() + err.getvalue()


class WebAdapterTest(unittest.TestCase):
    def _html(self, tmp: Path) -> Path:
        path = tmp / "page.html"
        path.write_text(HTML, encoding="utf-8")
        return path

    def test_local_html_to_sections_and_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            deck = from_web_points(self._html(Path(tmp)))
            self.assertEqual(deck.source_kind, "web")
            self.assertEqual(deck.card_count, 3)
            self.assertEqual(set(deck.sections), {"网络基础", "应用层"})
            cards = [c for cards in deck.sections.values() for c in cards]
            self.assertEqual([c["source"] for c in cards], ["block:2", "block:3", "block:5"])
            self.assertEqual(cards[0]["q"], "什么是TCP？")
            self.assertEqual(cards[0]["a"], "面向连接、可靠传输")

    def test_manifest_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            html = self._html(Path(tmp))
            manifest = ingest_mod.ingest_html(html, out=Path(tmp) / "ing.json",
                                              repo_root=Path(tmp)).out_path
            deck = from_web_points(manifest)
            self.assertEqual(deck.card_count, 3)
            self.assertEqual(deck.sections["网络基础"][0]["source"], "block:2")

    def test_no_points(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "plain.html"
            path.write_text("<html><body><p>只有普通段落</p></body></html>", encoding="utf-8")
            with self.assertRaises(Exception) as ctx:
                from_web_points(path)
            self.assertIn("没有解析出编号点", str(ctx.exception))

    def test_directory_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(Exception):
                from_web_points(Path(tmp))

    def test_wrong_suffix(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "a.txt"
            path.write_text("1. **X**：Y\n", encoding="utf-8")
            with self.assertRaises(Exception):
                from_web_points(path)

    def test_bad_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.json"
            path.write_text(json.dumps({"format": "pdf", "units": []}), encoding="utf-8")
            with self.assertRaises(Exception):
                from_web_points(path)


class WebAdapterCliTest(unittest.TestCase):
    def test_import_check_and_build(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            html = tmp / "page.html"
            html.write_text(HTML, encoding="utf-8")
            out = tmp / "deck"
            code, output = run_cli(["import", str(html), "--adapter", "web-points",
                                    "--out", str(out), "--name", "Web 测试"])
            self.assertEqual(code, 0, output)
            manifest = ingest_mod.ingest_html(html, out=tmp / "ing.json",
                                              repo_root=tmp).out_path
            code, output = run_cli(["check", str(out), "--html", str(html),
                                    "--ingest", str(manifest)])
            self.assertEqual(code, 0, output)
            code, output = run_cli(["build", str(out), "--out", str(tmp / "x.apkg"),
                                    "--html", str(html), "--ingest", str(manifest)])
            self.assertEqual(code, 0, output)
            self.assertTrue((tmp / "x.apkg").is_file())

    def test_import_with_ingest_folds_list_items(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            html = tmp / "page.html"
            html.write_text(
                "<html><body><h2>部署</h2>"
                "<p>1. **启动**：执行命令</p>"
                "<ul><li>先改配置</li><li>再重启</li></ul>"
                "</body></html>", encoding="utf-8")
            manifest = ingest_mod.ingest_html(html, out=tmp / "ing.json",
                                              repo_root=tmp).out_path
            out = tmp / "deck"
            code, output = run_cli(["import", str(html), "--adapter", "web-points",
                                    "--ingest", str(manifest), "--out", str(out)])
            self.assertEqual(code, 0, output)
            cards = json.loads(
                (out / "cards" / "01.json").read_text(encoding="utf-8"))["cards"]
            self.assertEqual(len(cards), 1, cards)
            self.assertEqual(cards[0]["source"], "block:2-4")
            self.assertIn("先改配置", cards[0]["a"])
            self.assertIn("再重启", cards[0]["a"])


if __name__ == "__main__":
    unittest.main()
