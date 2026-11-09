---
name: anki-card-builder
description: 从文本型 PDF、DOCX、TXT 或结构化 Markdown 题库构建并校验可直接导入 Anki 的 .apkg 卡组。当用户要求把学习资料做成 Anki 卡片/卡组、重打包已有卡组，或排查 .apkg 导入/重复卡问题时使用；不适用于扫描件 OCR、网页抓取，或非“标题+编号点”结构的任意文本自动抽卡。
---

# Anki 卡组构建

## 这个 skill 做什么

把一份学习资料变成可导入 Anki/AnkiDroid 的 `.apkg`，并在交付前验证结构。

核心链路只有一条：

```
资料 → 可寻址文本/结构化数据 → <deck>/cards/*.json → build → verify → 真机导入
```

PDF/DOCX/TXT/MD 只是入口不同，最后都汇入同一个 `DeckSpec` 和同一个构建入口。不要为一份新资料另写一个生成脚本。

## 何时用

- 用户给出文档（文本型 PDF、DOCX、TXT、结构化 Markdown 题库），要求生成 Anki 卡片/卡组/背诵卡。
- 已有 `cards/*.json` 卡组，要改卡片、重新打包、生成预览。
- `.apkg` 导入失败、重复卡、重复牌组、媒体缺失，需要定位。
- 需要把资料里的页码/段落/表格行做成可对账的 `source` 或页面截图。

## 何时不用

- 扫描版 PDF：没有文本层，本工具不做 OCR；直接说明无法处理。
- 加密 PDF/DOCX：先让用户解密，本工具不破解。
- 任意网页：没有 URL ingest；先保存为 Markdown，再按 Markdown 题库处理。
- 非“标题 + 编号点”结构的任意 TXT：不要承诺“自动抽卡”；`txt-points` 只认确定性格式。
- 事实校对、内容取舍、能不能公开：这些是人的判断，代码只保证结构。

## 前置条件

1. 需要本仓库的 checkout；`ankicards` 包不在 skill 目录里，skill 不能独立运行。
2. Python 3.12。
3. 安装核心依赖：

   ```bash
   python3 -m pip install -r requirements.txt
   ```

4. 需要 PDF 页面截图/裁图时，再安装渲染依赖：

   ```bash
   python3 -m pip install -r requirements-render.txt   # PyMuPDF
   ```

5. 所有命令从仓库根目录运行；若 agent 的工作目录不同，先 `cd` 到仓库根目录，或把仓库根加入 `PYTHONPATH`。
6. 公开复现材料在 `data/Android/`、`data/MQTT/`；非公开材料只放本地目录并加入本机忽略规则，不提交、不发布。

## 先选路径

| 输入 | 路径 | 关键命令 |
|---|---|---|
| 文本型 PDF 手册/讲义 | `ingest` 出逐页文本 → 人或 agent 写 cards → 构建时带 `--pdf`/`--ingest` | `ingest` → `check` → `build` |
| DOCX（标题 + 编号点/表格） | `ingest` 出定位 → `import --adapter docx-points` 或手写 cards | `ingest` → `import` → `check` → `build` |
| TXT（标题 + 编号点） | `ingest` 出行号 → `import --adapter txt-points` 或手写 cards | `ingest` → `import` → `check` → `build` |
| 结构化 Markdown 题库 | `import --adapter android-md` 或 `mqtt-md` | `import` → `check` → `build` |
| 已有 cards JSON | 直接校验/重打包 | `check` → `build` → `verify` |
| 图片题 | `crops.json` 定裁图框，构建必须给 `--pdf` | `check/build --pdf --ingest` |

`txt-points` 只接受“标题 + `1. **关键词**：解释`”结构；`import --list` 是适配器列表的唯一真值。

## 工作流

### 1. 确认输入与目标

确认源文件存在、格式属于上表哪一行、目标 deck 目录在哪里、是否需要图片题。

**完成标准**：能明确说出输入类型、源文件路径、目标 deck 目录、是否需要 `--pdf`/`--docx`/`--txt`/`--ingest`。

### 2. 产出可寻址文本或结构化卡片

- PDF：`python3 -m ankicards ingest <手册.pdf>`；默认写 `.work/ingest/<名字>-<sha8>.json`。
- DOCX：`python3 -m ankicards ingest <笔记.docx>`；得到 `para:N` / `table:T/rR`。
- TXT：`python3 -m ankicards ingest <笔记.txt>`；默认 UTF-8，旧文件用 `--encoding gb18030`；得到 `line:N`。
- 结构化 MD：直接 `import --adapter`，不要先 ingest。
- TXT/网页抓取：TXT 先 ingest 再 `txt-points`；网页仍不支持 URL ingest，先保存为 Markdown/TXT。

**完成标准**：文本/定位清单已生成；`check` 能读到 `<deck>/cards/*.json`。

### 3. 写卡片或导入卡片

- 手写：卡片写进 `<deck>/cards/*.json`，一卡一问。
- PDF 用 `pages`；非 PDF 用 `source`；`source_kind=docx` 时 `source` 必须是 `para:N` 或 `table:T/rR`，`source_kind=txt` 时必须是 `line:N`，并与 ingest 对齐。
- 图片题先在 `crops.json` 写 `page` + `rect`。

**完成标准**：没有未知字段；qa/image 的 q/a 齐全；每条溯源都能被 `check --ingest` 接受。

### 4. 裁图自检（仅图片题）

把所有裁图拼成一张 contact sheet 目视检查。裁框宁可窄不可宽；一张图里出现两个款式会直接产生错误答案。

**完成标准**：全部裁图过目，框内只有目标对象，没有相邻款式/文字。

### 5. check → build → verify → 真机导入

```bash
python3 -m ankicards check  <deck> [--pdf 手册.pdf|--docx 笔记.docx|--txt 笔记.txt] [--ingest .work/ingest/xxx.json]
python3 -m ankicards build  <deck> --out output/xxx.apkg [--pdf 手册.pdf|--docx 笔记.docx|--txt 笔记.txt] \
                            [--ingest .work/ingest/xxx.json] [--lite] [--preview preview.html]
python3 -m ankicards verify output/xxx.apkg
```

**完成标准**：`check` 0 error；`build` 成功；`verify` 0 error；Anki/AnkiDroid 导入一次，媒体 `Missing files: 0`。

### 6. 事实校对与记录

按页/按段抽查事实，记录校对基于哪一版数据（内容 hash 或 git commit）。没有这个记录，改一张卡就要整份重来。

**完成标准**：抽查记录可复述；校对基准已写入交付说明。

## 命令参考

| 命令 | 用途 | 备注 |
|---|---|---|
| `python3 -m ankicards ingest <pdf|docx|txt>` | 生成逐页/逐段/逐行文本清单 | PDF 仅文本型；DOCX 上限 20 MB / 解压后 200 MB / 5000 块；TXT 上限 10 MB / 50000 行，`--encoding` 指定编码 |
| `python3 -m ankicards import --list` | 列出适配器 | 当前：`android-md`、`mqtt-md`、`docx-points`、`txt-points` |
| `python3 -m ankicards import <src> --adapter <name> --out <deck>` | 源格式 → cards JSON | 已有卡片时需 `--force` 才覆盖 |
| `python3 -m ankicards check <deck>` | 数据契约校验 | 加 `--pdf` 查页码/裁图；加 `--ingest` 开溯源闸门；`--txt`/`--docx` 做同源校验 |
| `python3 -m ankicards build <deck> --out x.apkg` | 构建 apkg | 有图片题必须 `--pdf`；引用 pages/docx/txt 定位必须 `--ingest` |
| `python3 -m ankicards preview <deck> --out x.html` | 单文件 HTML 预览 | 与 build 相同的闸门 |
| `python3 -m ankicards verify x.apkg` | 解包做结构审计 | 不需要源数据；`--json` 输出机器可读结果 |

**退出码**：

- `0` 成功。
- `1` 数据/闸门失败（schema 错误、未过 `--ingest`、verify 结构错误）。
- `2` 用法/环境错误（缺必填参数、坏 JSON、PDF/DOCX/TXT 不可读或编码错误、有图片题却缺 `--pdf`、apkg 不是 zip）。

`check`/`verify` 全绿只证明结构正确，不证明事实正确。

## 牌组目录与契约

```
<deck>/
  deck.json        # 可选：{"name": "顶层牌组名", "source_kind": "pdf"}
  cards/*.json     # 必需：{"deck": "子牌组名", "cards": [...]}
  crops.json       # 可选：图片题的 page + rect
```

字段定义以 `ankicards/schema.py` 为唯一真值；这里不复制字段表，避免文档与代码漂移。新增字段先改代码与测试，再写文档。

定位语义：

- `pages` 只表示 PDF 页码；`source_kind=md/txt/docx/image` 时写 `pages` 会报错；`unknown` 兼容放行但会给 warning。
- `source` 用于非 PDF 溯源；`source_kind=docx` 时必须匹配 `para:N` 或 `table:T/rR`，`source_kind=txt` 时必须匹配 `line:N`，且能在 ingest 产物中找到、文本非空。
- `pages` 和 `source` 可以并存：前者出截图，后者给段落级定位。

## 依赖与相关文件

- `ankicards/`：CLI 与校验/构建逻辑，skill 的外部依赖。
- `requirements.txt`：`genanki`、`python-docx` 等核心依赖。
- `requirements-render.txt`：PyMuPDF，仅 PDF 截图/裁图需要。
- `ankicards/schema.py`：卡片字段与定位契约的唯一真值。
- `README.md`：安装、工具链与数据说明。
- `skills/README.md`：skill 安装与运行目录说明。
- 没有其他 skill 依赖本 skill；安装说明见 `skills/README.md`。

## 常见坑

| 现象 | 原因 / 处理 |
|---|---|
| AnkiDroid 报“不是有效的卡组文件” | 微信/QQ 把 `.apkg` 改名成 `apk.1`，改回 `.apkg` |
| 重建后 Anki 里出现重复卡 | 身份规则变了：guid 由 `identity_seed` 决定；不要改已发布牌组的身份规则 |
| 重新导入后出现重复牌组 | deck ID 不稳定；本工具链用确定性 ID，不要改已发布牌组的名字 |
| 构建报 `Tag contains a space` | Anki 标签不能含空格；构建器会自动把空格换成 `_` |
| 没有 PDF 时构建失败 | 牌组含图片题；提供 `--pdf`，或先移除图片题 |
| DOCX 一张卡都没解析出来 | Word 自动编号不在段落文本里；改为手写 `1. **关键词**：解释` 或粘贴编号 |
| DOCX 被拒绝 | 压缩包 >20 MB、解压后 >200 MB、>5000 块，或文件损坏/加密 |
| `unknown` 牌组带 `para:N`/`line:N` 却过不了 build | 声明 `source_kind=docx/txt` 并提供 `--ingest`；unknown 不再绕过定位闸门 |
| TXT 解码失败 | 默认 UTF-8；旧文件用 `--encoding gb18030`，或先转存 UTF-8 |
| `verify` 报父卡组缺失 | warning：Anki 导入时会自动创建父卡组 |
| `verify` 报 markdown 转义残留 | 字段里有 `\<`、`\>` 之类未转义残留，修数据 |

## 交付前验收

- `check` 0 error，且每条 warning 都能解释。
- `build` 成功，`verify` 0 error。
- 真机/Anki 导入一次：媒体 `Missing files: 0`。
- 连续两次构建，deck ID 与 guid 集合完全一致。
- 事实校对基准（hash 或 commit）已记录。

## 公开数据与发布

- 公开材料放 `data/Android/`、`data/MQTT/`，便于他人复现。
- 非公开材料只放本地私有目录，加入本机 `.git/info/exclude`；只在本机构建，不入库、不发布。
- 含内页截图的 `.apkg` 和预览 HTML 同样按机密处理。
