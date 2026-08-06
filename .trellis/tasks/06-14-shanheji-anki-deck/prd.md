# 山河集文档抽取为Anki卡组

## Goal

将 `data2/山河集/` 下7个TXT文件（FABE框架+10个产品系列总览+4个系列详细话术）抽取为Anki闪卡，输出为"山河集"卡组 `.apkg` 文件。

## What I already know

* 7个源文件均为中文TXT，UTF-8编码，内容自包含（Q&A都在原文中，无需AI生成）
* 现有流水线（TxtParser）专为Android面试设计，依赖AI生成答案，不适合此场景
* 需要新建专用解析器 `src/parsers/shanheji.py`
* 输出格式为 genanki `.apkg`，现有 `AnkiExporter` 可复用

## 源文件内容结构

| 文件 | 内容类型 | 预计卡片数 |
|------|---------|-----------|
| 04 FABE 话术框架.txt | FABE方法论（4个要素定义） | ~8 |
| 04 主系列产品一览.txt | 5个系列概览（灵感+标语+工艺） | ~15 |
| 04 主系列产品一览（续）.txt | 5个系列概览 | ~15 |
| 04 无尽夏系列.txt | FABE详情+完整话术 | ~10 |
| 04 花丝系列.txt | FABE详情+完整话术 | ~10 |
| 04 山河系列.txt | FABE详情+完整话术 | ~10 |
| 04 月洞系列.txt | FABE详情+完整话术 | ~10 |

**预计总计：~78张卡片**

## Requirements

* [ ] 新建 `src/parsers/shanheji.py` — 山河集TXT专用解析器
* [ ] 解析FABE框架文件，生成方法论知识卡片
* [ ] 解析产品一览文件，生成每个系列的灵感/标语/工艺卡片
* [ ] 解析系列FABE详情文件，生成 Feature/Advantage/Benefit/Evidence 卡片
* [ ] 解析完整话术示范，提取关键销售话术卡片
* [ ] 全部卡片归入"山河集"牌组（子牌组按主题分：FABE框架/产品系列/FABE话术）
* [ ] 输出 `output/山河集卡组.apkg`

## 卡片设计

### 卡片格式：Basic Q&A + Cloze 填空（混合）

**Basic Q&A** — 用于知识点考核：
- FABE卡片：`FABE中的F代表什么？` → Feature/特点/工艺设计特别之处
- 产品卡片：`无尽夏系列的灵感来源是什么？` → 无尽夏绣球花
- 话术卡片：`花丝系列的Advantage是什么？` → 扭丝肌理打破传统黄金的厚重刻板...

**Cloze 填空** — 用于完整话术示范中的关键短语记忆：
- `绣球花的花语是{{c1::希望}}，这件很适合{{c1::送给自己}}，或者送给{{c1::你在乎的人}}`
- `黄金代表{{c1::山}}，宝石代表{{c1::河}}，山代表{{c1::永恒}}，河代表{{c1::长久}}`

### 牌组结构
```
山河集
├── 山河集::FABE框架        （方法论 Basic Q&A）
├── 山河集::产品系列        （10个系列概览 Basic Q&A）
└── 山河集::FABE话术        （4个系列 FABE详情Basic + 话术Cloze）
```

## Decision (ADR-lite)

**Context**: 山河集TXT文件格式规整（F/Feature、A/Advantage 等标记），内容自包含，答案无需AI生成。

**Decision**: 新建 `src/parsers/shanheji.py` 专用解析器，纯正则匹配抽取，不调用AI。在 `pipeline.py` 的 `process_file()` 中注册 `.txt` 文件判断逻辑（检测是否为山河集文件）。

**Consequences**: 新增一个解析器文件，修改 `pipeline.py` 一处路由逻辑，简单直接。

## Technical Approach

1. 新建 `src/parsers/shanheji.py`
2. 按文件内容类型实现3种解析模式：
   - `_parse_fabe_framework()` — 解析FABE方法论
   - `_parse_product_overview()` — 解析产品系列一览
   - `_parse_series_fabe()` — 解析单系列FABE详情+话术
3. 在 `pipeline.py` 中增加山河集路由判断
4. 修改 `config.py` 增加山河集输出配置，或在调用时传参覆盖

## Out of Scope

* 不做AI答案生成（内容已自包含）
* 不修改现有 Android 面试流水线逻辑
* 不调用AI生成答案（内容均已自包含）

## Technical Notes

* 现有模型ID/Deck ID在 `config.py` 中硬编码，山河集需要新的ID范围避免冲突
* `AnkiExporter.export()` 已支持多牌组输出，可直接复用
* 山河集文件特征：文件名含"山河集"目录，或内容含"FABE"/"系列"关键词
