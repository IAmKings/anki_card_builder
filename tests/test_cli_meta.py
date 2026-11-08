"""测试布局：exit-2 用例不能被 PyMuPDF 依赖误跳过。"""

import unittest
from pathlib import Path

from tests import test_cli as cli_tests


class CliTestLayoutTest(unittest.TestCase):
    def test_exit_code_cases_are_not_skipped(self):
        cls = getattr(cli_tests, "CliExitCodeTest", None)
        self.assertIsNotNone(
            cls, "应存在 CliExitCodeTest：空源/拒绝覆盖这类 exit-2 用例不能挂在 skipUnless 类上")
        self.assertTrue(hasattr(cls, "test_empty_source_is_exit_2"))
        self.assertFalse(getattr(cls, "__unittest_skip__", False))

    def test_skip_decorator_belongs_to_gate_class(self):
        source = Path(cli_tests.__file__).read_text(encoding="utf-8")
        marker = '@unittest.skipUnless(HAS_PYMUPDF, "需要 PyMuPDF")'
        self.assertIn(f"{marker}\nclass GateCliTest", source)
        self.assertNotIn(f"{marker}\nclass CliExitCodeTest", source)


if __name__ == "__main__":
    unittest.main()
