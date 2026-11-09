"""发布工作流契约：P0 的根因是「上传物没有从 HEAD 构建」。

这些测试不解析 YAML，只守住几个不能退化的文本契约：
- release 必须调用从源码构建的脚本，并做 golden identity 校验；
- 上传物必须来自脚本输出目录，不能再 find output 全量上传；
- Release notes 必须带旧牌组删除说明；
- CI 必须有一个独立的公开牌组 identity job。
"""

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / ".github" / "workflows" / "release.yml"
VERIFY = ROOT / ".github" / "workflows" / "verify.yml"


class ReleaseWorkflowTest(unittest.TestCase):
    def setUp(self) -> None:
        self.release = RELEASE.read_text(encoding="utf-8")
        self.verify = VERIFY.read_text(encoding="utf-8")

    def test_release_builds_public_decks_from_source(self) -> None:
        self.assertIn("scripts/build_public_decks.py", self.release)
        self.assertIn("--check-golden", self.release)

    def test_release_uploads_only_script_output(self) -> None:
        self.assertIn("dist/Android.apkg", self.release)
        self.assertIn("dist/MQTT.apkg", self.release)
        self.assertNotIn("find output", self.release)
        self.assertNotIn("output/Android面试卡组.apkg", self.release)
        self.assertNotIn("output/MQTT协议卡组.apkg", self.release)

    def test_release_has_deck_migration_warning(self) -> None:
        self.assertIn("删除", self.release)
        self.assertIn("Android面试", self.release)
        self.assertIn("MQTT协议", self.release)
        self.assertIn("重复", self.release)

    def test_release_has_known_limitation(self) -> None:
        # v0.3.2 是 P0-only；闸门同源绑定留到 v0.3.3，必须在发布说明里写清楚
        self.assertIn("已知限制", self.release)
        self.assertIn("--ingest", self.release)

    def test_ci_has_public_deck_identity_job(self) -> None:
        self.assertIn("public-decks", self.verify)
        self.assertIn("scripts/build_public_decks.py", self.verify)
        self.assertIn("--check-golden", self.verify)


if __name__ == "__main__":
    unittest.main()
