"""公开牌组身份回归：默认跳过重构建，CI/发版前用环境变量显式启用。

完整的 Android/MQTT 重建约十几秒，不适合每个单元测试都跑；默认测试只校验
golden 文件本身。CI 的 public-decks job 和发布 workflow 会直接调用脚本。
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GOLDEN = ROOT / "tests" / "golden" / "public_decks.json"


class PublicDeckGoldenTest(unittest.TestCase):
    def test_golden_has_both_public_decks(self) -> None:
        payload = json.loads(GOLDEN.read_text(encoding="utf-8"))
        self.assertEqual(payload["schema"], 1)
        self.assertEqual(set(payload["decks"]), {"android", "mqtt"})
        # Android：1270 知识 + 326 填空 + 651 选择 + 58 对比
        self.assertEqual(payload["decks"]["android"]["notes"], 2305)
        # MQTT：200 知识 + 30 填空 + 78 选择
        self.assertEqual(payload["decks"]["mqtt"]["notes"], 308)

    @unittest.skipUnless(
        os.environ.get("RUN_PUBLIC_DECK_IDENTITY") == "1",
        "设置 RUN_PUBLIC_DECK_IDENTITY=1 才重建公开牌组",
    )
    def test_rebuild_matches_golden(self) -> None:
        with tempfile.TemporaryDirectory(prefix="public-decks-") as tmp:
            proc = subprocess.run(
                [sys.executable, "scripts/build_public_decks.py",
                 "--out", tmp, "--check-golden"],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("golden 身份校验通过", proc.stderr)


if __name__ == "__main__":
    unittest.main()
