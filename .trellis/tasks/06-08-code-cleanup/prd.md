# 深度清理项目代码

## Goal

重构项目结构：拆分 main.py 为模块化架构，清理中间文件，合并冗余脚本。

## Requirements

* 拆分 main.py 为 src/ 模块（parsers/ processing/ export/）
* 合并 rebuild_apkg.py / knowledge_ai_processor.py / generate_kotlin_cards.py 功能到模块
* 清理 output/（只保留 .apkg）
* 清理缓存文件
* main.py 保持为入口，内部 import src 模块
