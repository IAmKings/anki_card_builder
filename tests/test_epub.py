"""EPUB ingest 与小说 profile 的回归测试。"""

from __future__ import annotations

import json
import unittest
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory

from ankicards.cli import main
from ankicards.ingest import ingest_epub, load_ingest
from ankicards.plan import check_plan

CONTAINER = """<?xml version="1.0"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles><rootfile full-path="OEBPS/content.opf"
    media-type="application/oebps-package+xml"/></rootfiles>
</container>
"""

OPF = """<?xml version="1.0"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="id">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:identifier id="id">demo</dc:identifier><dc:title>演示</dc:title>
    <dc:language>zh</dc:language>
  </metadata>
  <manifest>
    <item id="c1" href="ch1.xhtml" media-type="application/xhtml+xml"/>
    <item id="c2" href="ch2.xhtml" media-type="application/xhtml+xml"/>
  </manifest>
  <spine><itemref idref="c1"/><itemref idref="c2"/></spine>
</package>
"""

CH1 = """<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml"><head><title>一</title></head>
<body><h1>第一章 启程</h1><p>他推开木门，院子里落着一层薄雪。</p><p>远处传来钟声。</p></body></html>
"""

LONG = "这是一段用于测试的小说正文，" * 30  # 420 字：超过 300，但在 novel 的 800 内
CH2 = f"""<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml"><head><title>二</title></head>
<body><h1>第二章 长夜</h1><p>{LONG}</p></body></html>
"""


def build_epub(root: Path) -> Path:
    path = root / "demo.epub"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("mimetype", "application/epub+zip")
        archive.writestr("META-INF/container.xml", CONTAINER)
        archive.writestr("OEBPS/content.opf", OPF)
        archive.writestr("OEBPS/ch1.xhtml", CH1)
        archive.writestr("OEBPS/ch2.xhtml", CH2)
    return path


class EpubIngestTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.epub = build_epub(self.dir)

    def test_ingest_reads_spine_in_order(self) -> None:
        result = ingest_epub(self.epub, out=self.dir / "ingest.json")
        manifest = result.manifest
        self.assertEqual(manifest["format"], "epub")
        self.assertEqual(manifest["chapter_count"], 2)
        self.assertEqual(manifest["chapters"][0]["title"], "第一章 启程")
        locators = [u["locator"] for u in manifest["units"]]
        self.assertEqual(locators[0], "chapter:1/p:1")
        self.assertIn("chapter:2/p:1", locators)
        kinds = {g["kind"] for g in manifest["groups"]}
        self.assertIn("paragraph", kinds)

    def test_load_ingest_registers_epub_locators(self) -> None:
        result = ingest_epub(self.epub, out=self.dir / "ingest.json")
        data = load_ingest(result.out_path)
        self.assertEqual(data.format, "epub")
        self.assertIn("chapter:1/p:3", data.locators)
        self.assertEqual(data.locators["chapter:1/p:2"], "他推开木门，院子里落着一层薄雪。")
        self.assertEqual(data.locators["chapter:1/p:3"], "远处传来钟声。")
        self.assertTrue(data.groups)

    def test_cli_ingest_dispatch(self) -> None:
        out = self.dir / "cli.json"
        self.assertEqual(main(["ingest", str(self.epub), "--out", str(out)]), 0)
        self.assertEqual(json.loads(out.read_text())["format"], "epub")


class NovelProfileTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.epub = build_epub(self.dir)
        self.ingest = load_ingest(ingest_epub(self.epub, out=self.dir / "i.json").out_path)

    def plan(self, quote: str, skip_reason: str = "plot_summary") -> dict:
        return {"version": 1, "deck": {"name": "小说", "source_kind": "epub"},
                "cards": [{"locator": "chapter:2/p:2", "quote": quote,
                           "q": "这一夜发生了什么？", "a": "长夜。"}],
                "skipped": [{"locator": "chapter:1/p:1", "reason": "heading"}]}

    def test_long_quote_rejected_by_default(self) -> None:
        report, _ = check_plan(self.plan(LONG), self.ingest)
        self.assertTrue(any("长度必须在 8–300" in e for e in report.errors))

    def test_novel_profile_relaxes_quote_and_reasons(self) -> None:
        plan = self.plan(LONG)
        plan["skipped"].append({"locator": "chapter:1/p:3", "reason": "plot_summary"})
        report, stats = check_plan(plan, self.ingest, profile="novel")
        self.assertEqual(report.errors, [])
        self.assertEqual(stats["cards"], 1)

    def test_novel_reason_rejected_without_profile(self) -> None:
        plan = self.plan("这一夜很漫长。")
        plan["skipped"].append({"locator": "chapter:1/p:3", "reason": "spoiler"})
        report, _ = check_plan(plan, self.ingest)
        self.assertTrue(any("spoiler" in e and "必须是" in e for e in report.errors))


if __name__ == "__main__":
    unittest.main()
