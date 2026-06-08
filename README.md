# Android 面试 Anki 卡组

> 市面上最完整的 Android 开发面试 Anki 卡片卡组，覆盖 Java、Android、网络、算法、设计模式等全方位知识点。

## 快速开始

### 1. 下载卡组

前往 [Releases](../../releases) 页面，下载最新的 `Android面试卡组.apkg`。

### 2. 导入 Anki

| 平台 | 说明 |
|------|------|
| **Android** | 安装 [AnkiDroid](https://github.com/ankidroid/Anki-Android) → 打开 → 导入 → 选择 .apkg |
| **iOS** | 安装 AnkiMobile → 同上 |
| **桌面** | 安装 [Anki](https://apps.ankiweb.net/) → 文件 → 导入 |

### 3. 开始复习

导入后卡片按技术领域自动分层，可根据需要选择牌组复习。

## 卡片统计

| 牌组 | 数量 |
|------|------|
| Android面试::Android | 255 张 |
| Android面试::Java | 161 张 |
| Android面试::算法与数据结构 | 12 张 |
| Android面试::网络 | 12 张 |
| Android面试::Kotlin | 11 张 |
| Android面试::综合 | 6 张 |
| Android面试::操作系统 | 1 张 |
| **总计** | **~460 张** |

## 内容来源

| 来源 | 说明 |
|------|------|
| 阿里巴巴 Android 面试题集 | 真题 + 答案解析，规则提取 |
| Android 核心知识点笔记 | 教科书式笔记，AI 生成问答 |
| 面试问题 TXT | 一面/二面真题，AI 补全答案 |

每张卡片标注来源，支持追溯。

## 卡片类型

- **基础问答**：正面问题 → 背面答案，适合概念记忆
- **Cloze 填空**：隐藏关键词，适合关键术语和数值

## 开发者

### 从源码构建

```bash
# 安装依赖
pip3 install pymupdf4llm genanki

# （可选）设置 API Key 获得更高质量的 AI 生成卡片
export ANTHROPIC_API_KEY='your-key'

# 运行流水线
python3 main.py

# 输出：output/Android面试卡组.apkg
```

### 项目结构

```
├── main.py                    # 核心流水线
├── knowledge_ai_processor.py  # AI 章节卡片生成器
├── rebuild_apkg.py            # 合并重建脚本
├── data/                      # 题库源文件
└── output/                    # 生成的 .apkg
```

### 贡献新题库

将 PDF 或 txt 文件放入 `data/` 目录，运行 `python3 main.py` 即可增量处理。新卡片会自动去重合并。

## License

MIT
