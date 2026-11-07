---
name: anki-card-builder
description: 把一份学习资料（PDF 手册/幻灯片、Markdown 题库、TXT）做成可分发的 Anki 卡组（.apkg）。当用户说"把这份资料做成 Anki 卡片/卡组/背诵卡"、"重新打包卡组"、"卡组导入失败要排查"时使用。覆盖选路径、卡片数据契约、图片题裁图、构建、导出后结构审计、机密材料处理。
---

# Anki 卡组构建

## 何时用

- 用户给出文档（PDF、MD、TXT、网页），要求生成 Anki 卡组 / 背诵卡 / `.apkg`
- 已有卡组要改卡片、重打包、排查导入问题

## 三条硬规则

1. **数据先进 JSON，再出包**。卡片内容写进 `<deck>/cards/*.json`，不要为一份新文档写一个新脚本。
2. **错了会静默产出坏包的事交给代码**：`check`（数据契约）、`build`（打包与媒体）、`verify`（导出后结构）。
3. **需要判断的事留给人**：怎么读新格式、图里裁哪里、事实对不对、能不能公开——这些代码判断不了，也不要假装能。

## 快速开始

```bash
python3 -m ankicards ingest <手册.pdf>          # 逐页文本，默认写 .work/ingest/
python3 -m ankicards check  <deck目录> [--pdf 手册.pdf] [--ingest .work/ingest/xxx.json]
python3 -m ankicards build  <deck目录> --out output/xxx.apkg [--pdf 手册.pdf] [--lite]
python3 -m ankicards verify output/xxx.apkg
```

- `ingest`：只支持**文本型 PDF**；加密/损坏/扫描件会 exit 2，不做 OCR。DOCX/MD/TXT 会被明确拒绝。
- `check`：只读数据；给了 `--pdf` 才检查页码上界与裁图越界；给了 `--ingest` 则启用**溯源闸门**——
  卡片引用的每一页必须出现在 ingest 产物里，且该页有文本。
- `build`：有图片题时**必须**给 `--pdf`（裁图要用源文件）；`--lite` 不生成原文页截图。
- `verify`：把 `.apkg` 解开做结构审计，不需要源数据，可对任何牌组使用。

## 牌组目录

```
<deck>/
  deck.json        # 可选：{"name": "顶层牌组名", "source_kind": "pdf"}
  cards/*.json     # 必需：{"deck": "子牌组名", "cards": [...]}
  crops.json       # 可选：图片题的裁图区域
```

**字段契约以 `ankicards/schema.py` 为唯一真值**，这里不复制字段表——复制一遍就一定会漂移。
新增字段先改代码与测试，再写进文档。

## 工作流

1. **读文档，选路径**：手册/讲义这类"内容要人来提炼"的，直接写 `cards/*.json`；已经是结构化题库（MD/TXT）的，先让 parser 产出同样的 `DeckSpec`，再走同一个 CLI。两条路最后汇入同一个构建入口。
2. **写卡片**：一卡一问。定位分两种：PDF 用 `pages`（背面截图、可被 ingest 对账）；非 PDF 用 `source`（文件名 > 章节 > 段落 id）。两者可并存，`source` 不会被丢掉。图片题先在 `crops.json` 里定 rect。
3. **裁图自检**：把所有裁图拼成一张 contact sheet 目视确认——框里只能有目标对象，一张图里出现两个款式会直接产生错误答案。
4. **check → build → verify → 真机导入一次**（Anki 桌面或 AnkiDroid）。
5. **事实校对**：按页抽查，记录校对基于哪一版数据（内容 hash 或 git commit），否则改一张卡就要整份重来。

## 能力边界（不要承诺超出这里的）

| 输入 | 行为 |
|---|---|
| 文本型 PDF | `ingest` 出逐页文本，可写卡、可出页面截图 |
| 扫描版 PDF | exit 2：无文本层，本工具无 OCR |
| 加密/损坏 PDF | exit 2：请先解密/修复 |
| DOCX | exit 2：Word 无“页”概念，表格/页眉未实现；先转 PDF |
| MD/TXT | 走 `import --adapter`，没有“自动抽卡” |

**ingest 只产出文本，不产出卡片。** 卡片仍由人或 agent 依据文本撰写；“PDF → 卡组”这句话只在
“ingest + 写卡 + build”整条流程里成立。

## 溯源闸门

`check --ingest <json>` 会拒绝三类假溯源：页码不存在、页码存在但该页无文本、非 PDF 来源写 `pages`。
未知卡片字段直接报错（白名单）。请把这条命令当作交付前的必跑项——`check`/`verify` 全绿只证明结构正确，
不证明事实正确。

## 图片题

- `rect` 是页面绝对坐标（pt），先粗后细；改完 rect 不需要清缓存——构建产物在临时目录，不存在"旧图复用"。
- 裁框宁可窄不可宽：宽了会把相邻款式带进来。
- 一次目视全部裁图，不要逐张点开。

## 数据与发布

- 公开资料放 `data/Android/` 之类可入库的目录，方便别人复现你的构建。
- 品牌内部手册等机密材料放在被 `.gitignore` 排除的目录（如 `data/江斯丹顿/`），**只在本机构建，不入库、不发布**。
- 含内页截图的 `.apkg` 和预览 HTML 同样按机密处理。

## 常见坑

| 现象 | 原因 / 处理 |
|---|---|
| AnkiDroid 报"不是有效的卡组文件" | 微信/QQ 把 `.apkg` 改名成 `apk.1`，改回 `.apkg` |
| 重新导入后出现重复牌组 | deck ID 不稳定；本工具链用确定性 ID（`ankicards/ids.py`），**不要改已发布牌组的名字** |
| 构建报 `Tag contains a space` | Anki 标签不能含空格；构建器会自动把空格换成 `_` |
| 没有 PDF 时构建失败 | 牌组含图片题；提供 `--pdf`，或先移除图片题 |
| `verify` 报父卡组缺失 | 这是 warning：Anki 导入时会自动创建父卡组 |
| `verify` 报 markdown 转义残留 | 字段里有 `\<`、`\>` 之类未转义的残留，建议修数据 |

## 交付前验收

- `check` 0 error，且每条 warning 都能解释
- `build` 成功，`verify` 0 error
- 真机/Anki 后端导入一次：媒体 `Missing files: 0`
- 连续两次构建，deck ID 与 guid 集合完全一致
