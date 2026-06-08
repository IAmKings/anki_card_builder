# PDF转Anki卡片 - Android面试知识卡组

## Goal

将 data 目录下的 PDF 和 txt 面试题内容提取出来，转换为 Anki 卡片（APKG 格式）。这是构建"市面上最完整的 Android 开发 Anki 卡片卡组"的第一步。

## Vision

成为市面上最完整的 Android 开发 Anki 卡片卡组，覆盖面试题、知识点、系统原理等全方位内容。

## Requirements

### 输入源
* `Android 核心知识点笔记.pdf` (352页，教科书式笔记，312个目录项)
* `阿里巴巴Android面试题集（答案解析）.pdf` (354页，已有问答格式)
* `android面试题.txt` (面试题大纲，只有题目)
* `面试问题.txt` (一面/二面面试题，只有问题)

### 转换策略
| 来源 | 策略 | 说明 |
|------|------|------|
| 阿里巴巴面试题集 | 规则解析 | 已有问答格式，正则提取 |
| 核心知识点笔记 | Claude API生成 | 按章节切分，AI生成问答对 |
| 2个txt | Claude API生成答案 | 先补全答案，再纳入卡片 |

### 卡片要求
* 每个PDF至少100张卡片（不含txt），总数预计250+
* 卡片类型：基础问答 + Cloze填空混合，AI自动选择
* 按技术领域分层牌组（如 `Android面试::Java`、`Android面试::网络`、`Android面试::多线程`）
* 每张卡片带标签（技术领域 + 来源）
* 来源标注：每张卡片标注来源文件和章节

### 质量保障
* 跨源去重：相似度>85%视为重复，合并标注多来源
* AI生成内容需标注来源，方便追溯校验
* 输出前人工抽检至少10张

### 可扩展性
* 代码架构支持增量处理：后续新增PDF/txt放入目录即可

## Decision (ADR-lite)

**Context**: 多源内容格式不同，需要不同策略；长期目标是完整卡组
**Decision**:
- 阿里巴巴面试题集 → 规则解析Q&A结构
- 核心知识点笔记 → pymupdf4llm提取 + Claude API生成问答
- txt面试题 → Claude API先生成答案，再纳入
- 牌组按技术领域分层（`Android面试::Java` 等）
- 卡片类型混合（问答 + Cloze），AI自动选择
- genanki 生成 .apkg 输出
**Consequences**: 卡片总数250+，AI成本约$1-2，架构需支持增量

## Acceptance Criteria

* [ ] 能成功读取并解析2个PDF + 2个txt
* [ ] 阿里巴巴面试题集解析出问答对
* [ ] 核心知识点笔记AI生成问答对
* [ ] txt面试题AI生成答案
* [ ] 每个PDF至少100张卡片
* [ ] 去重逻辑正常工作
* [ ] 输出.apkg可被Anki正常导入
* [ ] 卡片按技术领域分牌组、带标签
* [ ] 每张卡片可追溯到来源

## Definition of Done

* 代码可运行，输出正确的.apkg文件
* 生成的卡片内容经过人工抽检（至少10张）
* README说明使用方法

## Out of Scope

* GUI/Web界面（纯命令行脚本）
* 图片/表格提取（PDF中的图片不处理）
* Anki同步上传

## Technical Approach

**技术栈**: Python 3 + pymupdf4llm (PDF提取) + Claude API (AI生成) + genanki (输出.apkg)

**流水线**:
1. PDF提取 → pymupdf4llm 转 Markdown
2. 结构分析 → 面试题集用正则解析Q&A / 知识笔记按标题切分章节 / txt直接读取
3. AI生成 → Claude API (知识笔记生成问答 + txt补全答案)
4. 质量校验 → 结构验证 + 去重(85%相似度阈值)
5. 导出 → genanki生成.apkg（按技术领域分层牌组）
6. 人工抽检

**关键技术参考**:
* research/anki-format-and-genanki.md — genanki API用法、.apkg内部格式
* research/pdf-to-anki-approaches.md — PDF提取、分块策略、质量保证
