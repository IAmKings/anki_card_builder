"""静态 HTML 提取与 web ingest 清单：block:N、确定性、限额与坏输入。"""

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from ankicards import ingest as ingest_mod
from ankicards.errors import CardError
from ankicards.ingest import IngestError, ingest, load_ingest
from ankicards.web import WebError, iter_html_blocks

HTML = """<!doctype html>
<html><body>
<nav>菜单</nav>
<h1>标题</h1>
<p>第一段 <b>加粗</b></p>
<ul><li>项目一<p>嵌套段</p></li><li>项目二</li></ul>
<table><tr><th>键</th><th>值</th></tr><tr><td>甲</td><td>乙</td></tr></table>
<footer>页脚</footer>
<script>bad()</script>
</body></html>
"""


class HtmlBlocksTest(unittest.TestCase):
    def test_blocks_order_kinds_and_text(self):
        blocks = list(iter_html_blocks(HTML))
        self.assertEqual([b.locator for b in blocks],
                         [f"block:{i}" for i in range(1, len(blocks) + 1)])
        self.assertEqual([b.kind for b in blocks],
                         ["heading", "paragraph", "list_item", "list_item",
                          "table_row", "table_row"])
        self.assertEqual(blocks[1].text, "第一段 加粗")
        self.assertEqual(blocks[2].text, "项目一 嵌套段")
        self.assertEqual(blocks[4].text, "键 | 值")
        self.assertEqual(blocks[5].text, "甲 | 乙")

    def test_noise_tags_removed(self):
        text = " ".join(b.text for b in iter_html_blocks(HTML))
        for noise in ("菜单", "页脚", "bad()"):
            self.assertNotIn(noise, text)

    def test_empty_blocks_are_skipped(self):
        blocks = list(iter_html_blocks("<body><p> </p><p>有</p><div></div></body>"))
        self.assertEqual([b.text for b in blocks], ["有"])
        self.assertEqual(blocks[0].locator, "block:1")

    def test_table_duplicate_cells_collapsed(self):
        blocks = list(iter_html_blocks("<table><tr><td>甲</td><td>甲</td><td>乙</td></tr></table>"))
        self.assertEqual(blocks[0].text, "甲 | 乙")

    def test_max_blocks(self):
        with self.assertRaises(WebError):
            list(iter_html_blocks("<body><p>1</p><p>2</p></body>", max_blocks=1))

    def test_bad_html_is_web_error(self):
        with self.assertRaises(WebError):
            list(iter_html_blocks(b""))


class WebIngestTest(unittest.TestCase):
    def _html(self, tmp: Path, body: str = HTML) -> Path:
        path = tmp / "page.html"
        path.write_text(body, encoding="utf-8")
        return path

    def test_manifest_units_and_determinism(self):
        with tempfile.TemporaryDirectory() as tmp:
            page = self._html(Path(tmp))
            out = Path(tmp) / "a.json"
            first = ingest_mod.ingest_html(page, out=out, repo_root=Path(tmp))
            data = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(data["format"], "web")
            self.assertEqual(data["source"], "page.html")
            self.assertEqual(data["unit_kind"], "block")
            self.assertEqual(data["unit_count"], len(data["units"]))
            self.assertEqual(data["units"][0]["locator"], "block:1")
            self.assertEqual(data["units"][0]["kind"], "heading")
            self.assertEqual(data["source_sha256"], ingest_mod.file_sha256(page))
            self.assertNotIn(str(Path(tmp)), out.read_text(encoding="utf-8"))
            second = ingest_mod.ingest_html(page, out=out, repo_root=Path(tmp))
            self.assertEqual(out.read_bytes(), first.out_path.read_bytes())
            self.assertEqual(second.out_path, first.out_path)

    def test_no_text_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            page = self._html(Path(tmp), "<body><script>bad()</script><p> </p></body>")
            with self.assertRaises(IngestError):
                ingest_mod.ingest_html(page, out=Path(tmp) / "a.json", repo_root=Path(tmp))

    def test_size_limit(self):
        with tempfile.TemporaryDirectory() as tmp:
            page = self._html(Path(tmp))
            with mock.patch.object(ingest_mod, "MAX_WEB_BYTES", 10):
                with self.assertRaises(IngestError):
                    ingest_mod.ingest_html(page, out=Path(tmp) / "a.json", repo_root=Path(tmp))

    def test_dispatch_html(self):
        with tempfile.TemporaryDirectory() as tmp:
            page = self._html(Path(tmp))
            result = ingest(page, out=Path(tmp) / "a.json", repo_root=Path(tmp))
            self.assertEqual(result.manifest["format"], "web")

    def test_load_ingest_web(self):
        with tempfile.TemporaryDirectory() as tmp:
            page = self._html(Path(tmp))
            out = Path(tmp) / "a.json"
            ingest_mod.ingest_html(page, out=out, repo_root=Path(tmp))
            data = load_ingest(out)
            self.assertEqual(data.format, "web")
            self.assertIn("block:1", data.locators)
            self.assertTrue(data.locators["block:1"])

    def test_load_ingest_rejects_duplicate_block(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "a.json"
            path.write_text(json.dumps({
                "format": "web",
                "units": [{"locator": "block:1", "text": "a"},
                          {"locator": "block:1", "text": "b"}],
            }), encoding="utf-8")
            with self.assertRaises(IngestError):
                load_ingest(path)


if __name__ == "__main__":
    unittest.main()
