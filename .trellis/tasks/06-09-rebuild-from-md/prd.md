# 基于标准 MD 文件重建 APKG

## Goal

只基于 data/ 下的标准 Q&A 格式 MD 文件，完整重建 APKG。

## Requirements

* 解析 2 个 Kotlin 协程 MD → 100 张卡片
* 输出干净的 .apkg
* 不依赖 PDF/txt（已移除）
