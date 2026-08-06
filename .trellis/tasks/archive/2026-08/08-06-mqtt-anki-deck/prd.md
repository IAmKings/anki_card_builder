# MQTT 知识卡组

## Goal

将 `data3_mqtt/MQTT_100_Key_Knowledge_Points.md`（100 条 MQTT 知识点）解析生成 Anki 卡组 `.apkg` 文件。每知识点生成 1 张基础 Q&A 卡 + 1 张选择题卡，共约 200 张卡片。

## What I already know

* 源文件：`data3_mqtt/MQTT_100_Key_Knowledge_Points.md`，17KB，100 条知识点
* 文件结构：
  - `## 一、MQTT 基础概念（1-15）` 等 10 个章节标题
  - 每条知识点格式：`序号. **关键词**：解释说明`
* 项目现有模式：
  - `KotlinMDParser` — 通用 MD Q&A 解析器（处理 `**问题**` + `**答案：**` 格式）
  - `ShanhejiParser` — 专用 TXT 解析器（硬编码业务逻辑）
  - `generate_shanheji.py` — 独立生成脚本（自带 genanki model、export、quality check）
  - `pipeline.py` — 主流水线，`discover_source_files()` 只扫描 `data/` 目录
* MQTT 文件格式与现有 `KotlinMDParser` 不兼容（非 Q&A 格式，而是术语-解释 格式）

## Decisions Made

* **卡片正面格式**：混合模式 — 定义型术语（全称、含义、概念）用 `什么是{关键词}？` 格式；列举型/特征型/说明型术语直出关键词
* **牌组结构**：单一牌组 `MQTT协议`，所有卡片放入同一牌组，用标签区分章节来源
* **实现方式**：独立脚本 `generate_mqtt.py`，参考 `generate_shanheji.py` 模式，不集成到 pipeline
* **卡片类型**：每知识点 = 1 基础 Q&A + 1 选择题，约 200 张卡片
* **选择题干扰项 + 扩展提示**：调用 Claude API 生成 3 个逼真干扰项 + 扩展提示（≤150 字）

## Requirements

* 解析 `data3_mqtt/MQTT_100_Key_Knowledge_Points.md` 100 条知识点
* 每知识点生成 2 张卡片：
  - **基础 Q&A 卡**（basic）：Front = 关键词/问题，Back = 解释
  - **选择题卡**（basic）：Front = 问题 + 4 选项（A/B/C/D），Back = 正确答案 + 扩展提示（≤150字）
* 选择题的 3 个干扰项 + 扩展提示由 Claude API 生成
* 输出 `output/MQTT协议卡组.apkg`
* 标签按章节分类（如 `MQTT::基础概念`、`MQTT::QoS`）
* 生成汇总报告

## Acceptance Criteria

* [ ] 成功解析 100 条知识点，生成约 200 张卡片
* [ ] 基础 Q&A 卡 front 包含关键词/问题，back 包含完整解释
* [ ] 选择题卡 front 包含问题+4选项，back 包含正确答案+扩展提示
* [ ] AI 生成的干扰项与正确答案相关且具迷惑性
* [ ] 扩展提示 ≤150 字
* [ ] 生成合法 `.apkg` 文件，可在 Anki 中导入
* [ ] 生成汇总报告（按章节统计 Q&A/选择题卡片数）

## Definition of Done

* lint / typecheck 通过
* 生成的 `.apkg` 可正常导入 Anki

## Out of Scope (explicit)

* Cloze 填空卡片
* 增量更新/去重
* 图片/代码块嵌入

## Technical Approach

* 独立脚本 `generate_mqtt.py`，参考 `generate_shanheji.py` 架构
* AI 选择题生成：批量调用 Claude API，每批处理多条知识点，降低 API 调用次数
* 选择题 Anki 呈现：Front=问题+4选项(A/B/C/D)，Back=正确答案+扩展提示
* 使用项目已有的 `CONFIG.api_key` / `CONFIG.api_model` 配置

## Technical Notes

* 参考文件：`src/parsers/kotlin_md.py`、`src/parsers/shanheji.py`、`generate_shanheji.py`
* 源文件路径：`data3_mqtt/MQTT_100_Key_Knowledge_Points.md`
* 知识点正则：`r'^(\d+)\.\s+\*\*(.+?)\*\*[：:]\s*(.+)'`
* 章节正则：`r'^##\s+[一二三四五六七八九十]+[、.]\s*(.+?)(?:（|$)'`
