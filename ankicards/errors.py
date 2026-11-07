"""统一错误类型：所有“可读错误 + 退出码”的异常都走这里。

约定（与 README/SKILL 的退出码表一致）：
- code=2：用法或环境错误（缺必填参数、文件不可读、坏 JSON、加密 PDF 等）
- 数据/闸门失败不走异常：由命令返回 1，便于打印完整校验报告
"""

from __future__ import annotations


class CardError(Exception):
    """可读错误；main() 捕获后打印到 stderr 并以 code 退出。"""

    code = 2

    def __init__(self, message: str, code: int = 2):
        super().__init__(message)
        self.code = code
