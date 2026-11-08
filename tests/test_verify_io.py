"""apkg 结构审计的错误路径：缺 collection、坏 media 都必须可读退出。"""

import contextlib
import io
import tempfile
import unittest
import zipfile
from pathlib import Path

from ankicards.cli import main

REAL_APKG = Path(__file__).resolve().parents[1] / "output" / "MQTT协议卡组.apkg"


def run(args):
    stderr = io.StringIO()
    with contextlib.redirect_stderr(stderr):
        code = main(args)
    return code, stderr.getvalue()


class VerifyIOTest(unittest.TestCase):
    def test_zip_without_collection_is_exit_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            apkg = Path(tmp) / "no-collection.apkg"
            with zipfile.ZipFile(apkg, "w") as archive:
                archive.writestr("media", "{}")
            code, err = run(["verify", str(apkg)])
            self.assertEqual(code, 2)
            self.assertNotIn("Traceback", err)
            self.assertIn("collection", err)

    @unittest.skipUnless(REAL_APKG.exists(), "需要已入库的 apkg 作为样本")
    def test_corrupt_media_json_is_exit_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "bad-media.apkg"
            with zipfile.ZipFile(REAL_APKG) as src, zipfile.ZipFile(bad, "w") as dst:
                for item in src.infolist():
                    if item.filename == "media":
                        continue
                    dst.writestr(item, src.read(item.filename))
                dst.writestr("media", "not json")
            code, err = run(["verify", str(bad)])
            self.assertEqual(code, 2)
            self.assertNotIn("Traceback", err)

    @unittest.skipUnless(REAL_APKG.exists(), "需要已入库的 apkg 作为样本")
    def test_real_apkg_still_passes(self):
        code, err = run(["verify", str(REAL_APKG)])
        self.assertEqual(code, 0, err)


if __name__ == "__main__":
    unittest.main()
