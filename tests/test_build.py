"""构建侧回归：裁图重名不得串图、图片题 guid 必须区分 img。"""

import json
import tempfile
import unittest
import zipfile
import sqlite3
from pathlib import Path

from ankicards.build import build
from ankicards.ingest import ingest_pdf
from ankicards.schema import load_spec

try:
    import pymupdf  # type: ignore
    HAS_PYMUPDF = True
except ImportError:  # pragma: no cover
    HAS_PYMUPDF = False


@unittest.skipUnless(HAS_PYMUPDF, "需要 PyMuPDF")
class BuildCollisionTest(unittest.TestCase):
    def test_crop_names_that_normalize_together_stay_distinct(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pdf = root / "s.pdf"
            doc = pymupdf.open()
            doc.new_page(width=200, height=200)
            doc.save(str(pdf))
            doc.close()

            deck = root / "deck"
            (deck / "cards").mkdir(parents=True)
            (deck / "cards" / "01.json").write_text(json.dumps({"deck": "S", "cards": [
                {"type": "image", "q": "哪张？", "a": "A", "img": "图1", "pages": [1]},
                {"type": "image", "q": "哪张？", "a": "B", "img": "表1", "pages": [1]},
            ]}, ensure_ascii=False), encoding="utf-8")
            (deck / "crops.json").write_text(json.dumps([
                {"name": "图1", "page": 1, "rect": [0, 0, 50, 50]},
                {"name": "表1", "page": 1, "rect": [100, 100, 150, 150]},
            ], ensure_ascii=False), encoding="utf-8")
            (deck / "deck.json").write_text(
                json.dumps({"name": "碰撞", "source_kind": "pdf"}, ensure_ascii=False),
                encoding="utf-8")

            out = root / "x.apkg"
            build(load_spec(deck), out, pdf=str(pdf), lite=False)

            with zipfile.ZipFile(out) as archive:
                archive.extractall(root / "extract")
            con = sqlite3.connect(str(root / "extract" / "collection.anki2"))
            rows = [r[0] for r in con.execute("select flds from notes")]
            con.close()

            import re
            images = [set(re.findall(r'src="([^"]+)"', row)) for row in rows]
            crop_files = [{i for i in imgs if "crop-" in i} for imgs in images]
            self.assertEqual(len(rows), 2)
            self.assertEqual(len(crop_files[0]), 1)
            self.assertEqual(len(crop_files[1]), 1)
            self.assertNotEqual(crop_files[0], crop_files[1], "两张图不得复用同一媒体文件")

    def test_image_cards_same_qa_different_img_have_distinct_guids(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pdf = root / "s.pdf"
            doc = pymupdf.open()
            doc.new_page(width=200, height=200)
            doc.save(str(pdf))
            doc.close()

            deck = root / "deck"
            (deck / "cards").mkdir(parents=True)
            (deck / "cards" / "01.json").write_text(json.dumps({"deck": "S", "cards": [
                {"type": "image", "q": "同一题干", "a": "同一答案", "img": "a", "pages": [1]},
                {"type": "image", "q": "同一题干", "a": "同一答案", "img": "b", "pages": [1]},
            ]}, ensure_ascii=False), encoding="utf-8")
            (deck / "crops.json").write_text(json.dumps([
                {"name": "a", "page": 1, "rect": [0, 0, 50, 50]},
                {"name": "b", "page": 1, "rect": [100, 100, 150, 150]},
            ], ensure_ascii=False), encoding="utf-8")
            (deck / "deck.json").write_text(
                json.dumps({"name": "身份", "source_kind": "pdf"}, ensure_ascii=False),
                encoding="utf-8")

            out = root / "x.apkg"
            build(load_spec(deck), out, pdf=str(pdf), lite=False)
            with zipfile.ZipFile(out) as archive:
                archive.extractall(root / "extract")
            con = sqlite3.connect(str(root / "extract" / "collection.anki2"))
            guids = [r[0] for r in con.execute("select guid from notes")]
            con.close()
            self.assertEqual(len(guids), 2)
            self.assertEqual(len(set(guids)), 2, "同题干同答案不同图必须是两张卡")


if __name__ == "__main__":
    unittest.main()
