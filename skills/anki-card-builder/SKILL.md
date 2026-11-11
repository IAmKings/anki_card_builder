---
name: anki-card-builder
description: 把文本型 PDF、DOCX、TXT、EPUB、静态 HTML 或结构化 Markdown 学习资料做成可导入 Anki 的 .apkg：ingest → 可卡性预检 → plan 抽取（每卡逐字 quote 校验）→ check → build → verify。当用户要求做卡组、把书/手册/讲义/小说做成本地 Anki 卡、重打包或增量更新已有卡组、排查 .apkg 导入/重复卡/溯源问题时使用；不适用于扫描件 OCR、需要登录或 JS 渲染的网页，也不承诺把任意散文零判断地自动抽成卡。
---

# Anki 卡组构建

## 这个 skill 做什么

把一份学习资料变成可导入 Anki/AnkiDroid 的 `.apkg`，并在交付前验证结构。

核心链路只有一条：

```
资料 → 可寻址文本/结构化数据 → <deck>/cards/*.json → build → verify → 真机导入
```

PDF/DOCX/TXT/Web/MD 只是入口不同，最后都汇入同一个 `DeckSpec` 和同一个构建入口。不要为一份新资料另写一个生成脚本。

## 何时用

- 用户给出文档（文本型 PDF、DOCX、TXT、结构化 Markdown 题库）或静态网页 URL，要求生成 Anki 卡片/卡组/背诵卡。
- 已有 `cards/*.json` 卡组，要改卡片、重新打包、生成预览。
- `.apkg` 导入失败、重复卡、重复牌组、媒体缺失，需要定位。
- 需要把资料里的页码/段落/表格行做成可对账的 `source` 或页面截图。

## 何时不用

- 扫描版 PDF、图片型 EPUB/漫画：没有文本层，本工具不做 OCR；直接说明无法处理。
- MOBI/AZW：没有 ingest 路径（未实现 PalmDOC 解析）。需要时先用 Calibre `ebook-convert` 转成 EPUB，转换步骤不进本仓库。
- 加密 PDF/DOCX：先让用户解密，本工具不破解。
- 需要登录、Cookie、JS 渲染或整站爬取的网页：本工具只抓单个静态 HTML；让用户保存页面/导出正文，或先用其他工具转成 Markdown/TXT。
- 散文/手册/讲义等非“标题 + 编号点”结构的内容：**禁止**走 `txt-points`/`docx-points`/`web-points`，也不要承诺“自动抽卡”。先 `ingest` 拿到定位，再逐条写卡，并逐条确认这个知识点真的成立；判定规则与失败模式见 [docs/extraction-policy.md](../../docs/extraction-policy.md)。
- 事实校对、内容取舍、能不能公开：这些是人的判断，代码只保证结构。

## 文档形态判定（先判形态，再选路径）

动手前先判这份资料属于哪一类，形态判错，后面全是白做。

| 形态 | 判据 | 路径 |
|---|---|---|
| 结构化题库 | 有成对的题干/答案、或“标题 + 编号点 + 冒号解释”的稳定版式 | 可走 `*-points` / `android-md` / `mqtt-md` |
| 手册 / 讲义 / 散文 | 成段叙述；编号点只是排版；有大量“因为/因此/通常/注意” | `ingest` → 写 `plan.json` → `plan compile`（推荐）；或逐条写卡（**不要**套 `*-points`） |
| 小说 / 电子书 | EPUB，章节 + 成段叙述 | `ingest book.epub` → 写 plan（`--profile novel`）→ `plan compile --profile novel --with-key` |
| 散文 / 随笔集 | EPUB 或纯文本，段落完整、无编号 | `ingest` → 写 plan（`--profile essay`，quote 上限 800）→ `plan compile --profile essay --with-key` |
| 已发布牌组 | 目录里有 `deck.json` 且已分发 | 只改卡不改身份；**禁止**用任何自动/生成式流程重跑 |

三条硬性红线：

1. **散文、手册、讲义禁止走 `*-points` 适配器。** 这类适配器按单行正则切点（`ankicards/adapters.py` 的 `_TXT_ITEM_*` / `_DOCX_ITEM_*`），把“版面结构”当成“知识单元结构”，会把步骤当概念、把续行和小项丢掉，而且这些坏卡能通过 `check`（闸门只验结构，不验可背性）。实测样本见 policy 文档。
2. **agent / LLM 不得直接写 `cards/*.json`。** 汇总、改写、归纳必须落在可审阅的 `plan.json` 上（每张卡都要带逐字 `quote`），再由 `plan check` / `plan compile` 做确定性校验并编译成卡。直接写卡等于把未校验的转述混进发布物。规则见 policy 文档 §8。
3. **已发布牌组不重跑抽取。** 身份由 `q`/`a` 文本决定，重写文本在 Anki 里就是新卡；要改卡请直接改卡面文本，不要重跑生成。

## 准入：先问用途，再动手

形态只回答「能不能自动抽」，用途才回答「该抽什么、抽多少、怎么验」。**没问清用途就开始写卡，等于替用户决定了他要背什么。**

动手前必须问清三件事，缺一条就停下来问：

1. **这份材料给谁、背来干什么？**（考试复述 / 工作查用 / 写作模仿 / 语言学习 / 情节复习 / 鉴赏）
2. **验收怎么算通过？**（答对率 / 能不能照着做 / 能不能照这个写法造一句 / 能不能复述出差异点）
3. **要不要防剧透、要不要保持原文顺序？**（小说、教程类必答）

拿到答案后查这张表，把「用途、卡型组合、密度带、验收方式」写进交付说明：

| 形态 + 用途 | 可用卡型 | `--density` 档 | 建议密度（字/张） | 验收方式 | 必须拒绝或改写的情况 |
|---|---|---|---|---|---|
| 手册 / 考试背诵 | `fact` `claim` | `manual` | 300–500 | 答对率 | 找不到可检验事实时明说，不要用观点卡冒充考点 |
| 手册 / 工作查用 | `fact` `procedure` | `manual` | 200–400 | 能不能照做 | 步骤跨页的要用 `page:N-M` 合并区间 |
| 讲义 / 写作模仿 | `style` `claim` | `essay` | 800–1,200 | 照着这个写法造一句 | 没有手法样本就记 `style_note`，不要硬凑 |
| 散文随笔 / 鉴赏复述 | `claim` `phrase` `style` | `essay` | 800–1,200 | 复述出差异点 | **不出 `fact`**：这类文本没有可检验的事实 |
| 小说 / 情节复习 | `fact` `claim` | `novel` | 500–800 | 按阅读顺序回忆 | 卡面不得出现本 locator 之后才登场的角色或结局 |
| 小说 / 人物分析 | `claim` `style` | `novel` | 600–1,000 | 能否给出证据句 | 剧透是允许的，但要在交付说明里标明 |
| 散文 / 「知识点归纳」 | — | — | — | — | **前置拒绝**：见下方「硬要抽知识点」 |
| 结构化题库 / 考试 | `fact` | `manual` | 50–200 | 答对率 | 表头行不当数据（Q7） |

表里的「建议密度」是**用途级**建议，必须落在所选 `--density` 档的区间内，否则 `plan check`
会提示太密或太疏：`manual` 200–700、`novel` 400–1200、`essay` 600–1600（数字只以代码
`DENSITY_BANDS` 为准，这里不重复维护）。题库型会低于 `manual` 的 200 下限，`plan check`
报「太密」属预期——题库本来就是一条信息点一张卡，按题库口径忽略这条提示。

四条停问红线（命中任意一条，停下来找用户确认，不要自己拍板）：

1. **用途缺失**：用户只说「做成卡片」。默认按「知识点」做，正是错配的来源。
2. **形态与用途冲突**：散文集要「知识点归纳」、小说要「考点」——先拒绝，再给替代口径。
3. **覆盖率异常**：某章覆盖率 <50%（漏读）或 >98% 且卡数明显偏少（敷衍判定）。
4. **抽样失败率 >30%**：不是单张卡的问题，是这批卡对该用途不成立，回去改口径。

`ingest` 之后再加一道可卡性预检（五个指标与阈值见
[docs/extraction-policy.md](../../docs/extraction-policy.md) §12）：指标推荐的卡型与用途
冲突时，**以用途为准**，但要说明为什么不用指标的建议。实测同一套算法下，散文集的数字句
占比 0.6%、技术手册 52%——这就是「同一套工具两种密度」的客观来源。

### 硬要抽知识点：先说清抽不出来什么

散文、随笔、小说做「知识点归纳」会必然失败，原因不在工具，在文本：

- 知识点要能独立判定真假；散文写的是**判断与感受**，没有真假，只有认同与否。
- 知识点要能互相连接成体系；散文是**一篇一境**，章与章之间没有依赖。
- 现成的数字校验（E2）只对 `fact` 有效；观点卡没有数字可查，规则形同虚设。

正确处理是**换口径**，不是换提示词：说明「这类文本能出的是观点、写法、金句，密度约 800–1,200 字/张（落在 `--density essay` 的 600–1600 档内），验收是能否复述出差异点」，再问用户是否接受；不接受就换资料，不要产出一批看起来像知识点的观点卡。

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
| DOCX（标题 + 编号点/表格） | `ingest` 出定位 → `import --adapter docx-points [--ingest 清单]` 或手写 cards | `ingest` → `import` → `check` → `build` |
| TXT（标题 + 编号点） | `ingest` 出行号 → `import --adapter txt-points [--ingest 清单]` 或手写 cards | `ingest` → `import` → `check` → `build` |
| 静态 Web（标题 + 编号点） | `ingest` 出块号 → `import --adapter web-points [--ingest 清单]`（本地 HTML 或 manifest）或手写 cards | `ingest` → `import` → `check` → `build` |
| 散文 / 手册 / 讲义（无编号点） | `ingest` 出定位 → 逐条写 cards；**不要**套 `*-points` | `ingest` → 写 cards → `check` → `build` |
| 结构化 Markdown 题库 | `import --adapter android-md` 或 `mqtt-md` | `import` → `check` → `build` |
| 已有 cards JSON | 直接校验/重打包 | `check` → `build` → `verify` |
| 图片题 | `crops.json` 定裁图框，构建必须给 `--pdf` | `check/build --pdf --ingest` |

`txt-points`/`web-points` 只接受“标题 + `1. **关键词**：解释`”结构；`import --list` 是适配器列表的唯一真值。

## 卡型与密度

写 plan 时给每张卡标 `kind`：`claim`（观点/判断）、`style`（写法/结构/语气）、
`phrase`（金句）、`fact`（事实/数字）、`procedure`（流程/步骤）。不同卡型的验收标准不同
（金句要能整句背、文风卡要有足够长的样本、事实卡要有可核对的数字、流程卡的问题要指向
动作或对象），`plan check` 会按卡型提醒。手册里“该找谁审批、要交什么材料、东西丢了怎么
办”属 `procedure`；别把流程硬压成 `fact`，它往往没有数字可核对。

密度跟着文体走，不要按字数硬凑：

- **知识型/考点型文档**（题库、规格、教程）：一条信息点一张卡，密度可以很高。
- **散文/随笔**：每篇 3–5 张是实测的合理区间，全书 40–70 张。同一段里前半观点、
  后半金句，可以出两张卡（quote 不重叠即可），不必二选一。
- 卡量超过「每 500 字一张」就要停下来问：是不是在把信息硬拆成卡片？注意力会被稀释。
- 想让这条判断可执行，用 `plan check --density {manual,novel,essay}`：按「读过的原文字数 / 卡数」
  算密度，散文 600–1600、手册 200–700、小说 400–1200；散文口径出现 `fact` 卡、手册口径
  `fact` 不足 30% 也会提示。它只给 warning，不拦编译。

## 工作流

### 1. 确认输入与目标

确认源文件存在、格式属于上表哪一行、目标 deck 目录在哪里、是否需要图片题；并按 §准入 问清用途与验收口径（形态 + 用途 = 允许卡型 + 密度带 + 验收方式）。

**完成标准**：能明确说出输入类型、源文件路径/URL、目标 deck 目录、是否需要 `--pdf`/`--docx`/`--txt`/`--html`/`--ingest`，以及**这次要背来干什么、用什么算通过、允许哪些卡型**。四项里缺「用途」时不要开工。

### 1.5 可卡性预检（10 秒，决定走哪条路）

```bash
python3 scripts/precheck.py --ingest .work/ingest/xxx.json [--json]
```

PDF 会先按行拆再算，否则一页上千字会把比例稀释成「编号点 0%」。

- 编号点 ≥30% 才考虑 `*-points`；PDF 还要先核对折行会不会切断「一问一答」，不成立就走 plan。
- 数字句 <3% → 不出 `fact`；>30% → `fact` 可为主力。
- 单页 >300 字的占比高 → 长引用会跨页，优先 EPUB 或用 `page:N-M`。

指标只用于选路，不进 `plan check`；和人工判断冲突时以人工判断为准，但要说明理由。

### 2. 产出可寻址文本或结构化卡片

- PDF：`python3 -m ankicards ingest <手册.pdf>`；默认写 `.work/ingest/<名字>-<sha8>.json`。清单里的 `page_spans` 列出「上一页没以句末标点收尾」的相邻页对，即疑似跨页续写的位置。
- DOCX：`python3 -m ankicards ingest <笔记.docx>`；得到 `para:N` / `table:T/rR`。
- TXT：`python3 -m ankicards ingest <笔记.txt>`；默认 UTF-8，旧文件用 `--encoding gb18030`；得到 `line:N`。
- Web（本地）：`python3 -m ankicards ingest <page.html>`；得到 `block:N`。
- Web（URL）：`python3 -m ankicards ingest <https://...>`；得到 `block:N` 与 `content_sha256`；默认拒绝内网，测试本机页面加 `--allow-private-network`。
- 结构化 MD：直接 `import --adapter`，不要先 ingest。
- 自动出卡：TXT 先 ingest 再 `txt-points`；Web 先 ingest，再从本地 HTML 或 ingest manifest 走 `web-points`，不要二次抓取。**仅限编号点结构**；散文/手册不适用，见 §文档形态判定。
- 续行与子项：ingest 会把「编号点 + 紧跟的缩进行/子项/没说完的上一行」归成一组（`groups`）。出卡时加 `--ingest` 让适配器按组取点：答案会把组内其余文本并进来，`source` 写成区间（如 `line:6-7`）。不加 `--ingest` 时行为与旧版一致（仍按单行切点，会丢续行）。

**完成标准**：文本/定位清单已生成；`check` 能读到 `<deck>/cards/*.json`。

### 3. 写卡片或导入卡片

- 文档抽取（推荐）：agent 只写 `plan.json`——每条要么是卡（`locator` + `quote` + `q`/`a`），要么是未出卡（`locator` + `reason`）。`quote` 必须从定位文本里逐字复制（空白差异忽略）；卡面里的数字必须出现在 `quote` 里。然后：
  ```bash
  python3 -m ankicards plan check  plan.json --ingest .work/ingest/xxx.json --min-coverage 0.9 [--density essay]
  python3 -m ankicards plan compile plan.json --out <deck> --ingest .work/ingest/xxx.json
  python3 -m ankicards plan diff    plan.json --deck <deck>   # 这次会新增/删除/改动哪些卡
  ```
  有 error 时 `compile` 拒绝写盘。`quote` 只留在 plan 里，不写进卡片（Anki 字段固定）。
- 手写：卡片写进 `<deck>/cards/*.json`，一卡一问。
- PDF 用 `pages`；跨页段落写 `page:N-M`（`plan compile` 会写成 `pages:[N, M]`，背面同时显示两页）；非 PDF 用 `source`；`source_kind=docx` 时 `source` 必须是 `para:N` / `para:N-M` / `table:T/rR`，`source_kind=txt` 时必须是 `line:N` 或 `line:N-M`，`source_kind=web` 时必须是 `block:N` 或 `block:N-M`，并与 ingest 对齐（区间必须整体出现在 ingest 里，起点不能大于终点）。
- 图片题先在 `crops.json` 写 `page` + `rect`。

小说用 `--profile novel` 时声明主要人物：`"entities": [{"name": "X", "locator": "chapter:3/p:1"}]`。
卡面在人物登场前提到它会被判 error；复制后文整句、提后文拉丁名会给 warning。
中文人名工具不猜——不声明就只做保守检查，别指望它替你发现所有剧透。

同一本书有 EPUB/PDF/TXT 多份时，用 `--also` 交叉校验：quote 在另一种格式里也要逐字命中
（`交叉 pdf 88/88（跨单元 3）`）。PDF 报「跨单元」不是错误，是换页切断——该格式单页无法整句溯源。

**完成标准**：走 plan 时 `plan check` 无 error、覆盖率与未出卡理由都说得通；直写卡片时没有未知字段、qa/image 的 q/a 齐全；每条溯源都能被 `check --ingest` 接受；`import-report.json` 里的 error 级可疑项都看过并解释过（不一定要清零，但不能没看）。

### 4. 裁图自检（仅图片题）

把所有裁图拼成一张 contact sheet 目视检查。裁框宁可窄不可宽；一张图里出现两个款式会直接产生错误答案。

**完成标准**：全部裁图过目，框内只有目标对象，没有相邻款式/文字。

### 5. check → build → verify → 真机导入

```bash
python3 -m ankicards check  <deck> [--pdf 手册.pdf|--docx 笔记.docx|--txt 笔记.txt|--html page.html] [--ingest .work/ingest/xxx.json]
python3 -m ankicards build  <deck> --out output/xxx.apkg [--pdf 手册.pdf|--docx 笔记.docx|--txt 笔记.txt|--html page.html] \
                            [--ingest .work/ingest/xxx.json] [--lite] [--preview preview.html]
python3 -m ankicards verify output/xxx.apkg
```

**完成标准**：`check` 0 error；`build` 成功；`verify` 0 error；Anki/AnkiDroid 导入一次，媒体 `Missing files: 0`。

### 6. 事实校对与记录

按页/按段抽查事实，记录校对基于哪一版数据（内容 hash 或 git commit）。没有这个记录，改一张卡就要整份重来。

**完成标准**：抽查记录可复述；校对基准已写入交付说明。

## 命令参考

全部能力都在 CLI 里，没有隐藏入口；`python3 -m ankicards <命令> --help` 是参数唯一真值。
agent 的标准链路：`precheck → plan check → plan compile → check → build → verify`。
`python3 -m ankicards --version` 打印版本号（0.4.0）。

| 命令 | 用途 | 备注 |
|---|---|---|
| `python3 -m ankicards ingest <pdf|docx|txt|html|url>` | 生成逐页/逐段/逐行/逐块文本清单 | PDF 仅文本型；DOCX 上限 20 MB / 解压后 200 MB / 5000 块；TXT 上限 10 MB / 50000 行；Web 5 MB / 5000 块 / 20 秒 / 5 次 redirect，静态 HTML |
| `python3 -m ankicards import --list` | 列出适配器 | 当前：`android-md`、`mqtt-md`、`docx-points`、`txt-points`、`web-points` |
| `python3 -m ankicards import <src> --adapter <name> --out <deck>` | 源格式 → cards JSON | 已有卡片时需 `--force` 才覆盖；同时写 `import-report.json`（未出卡理由 + 内容规则命中）；`--strict` 让 error 级内容问题直接失败且不写牌组；`--ingest` 按 ingest 的分组合并续行/子项，并校验源文件 sha256 |
| `python3 scripts/precheck.py --ingest <清单>` | 可卡性预检：编号点/数字句/段长/引号/表格行 | PDF 先按行拆再算（按页算会把比例稀释成 0%）；只给选路建议，不改仓库 |
| `python3 -m ankicards plan check <plan.json> --ingest <清单> [--also <另一格式清单>] [--profile manual\|novel\|essay] [--density manual\|novel\|essay]` | 校验引用锚定/理由枚举/覆盖率/密度/跨格式一致性/剧透 | 每条卡必须有 `quote`；数字按数值比对（「三天」=「3 天」），写法不同只提示；同一定位可以出多张卡，但 `quote` 不得重叠；`--min-coverage` 设分组覆盖率下限；`--density` 只提示密度与卡型配额（不拦编译）；`--also` 拿 quote 去另一种格式里重找，验证内容一致 |
| `python3 -m ankicards plan compile <plan.json> --out <deck> --ingest <清单> [--profile ...] [--density ...] [--with-key] [--incremental]` | 校验通过才写牌组 | 有 error 不写盘；同时写 `import-report.json`（未出卡理由 + 内容规则）；`--with-key` 生成稳定身份；`--incremental` 并进已有牌组（按 key 替换、按 `retired` 下架、其余保留） |
| `python3 -m ankicards plan diff <plan.json> --deck <deck>` | 对比 plan 与现有牌组 | 按归一后的卡面文本比对，报告新增/删除/改动；退出码恒为 0 |
| `python3 -m ankicards check <deck>` | 数据契约校验 | 加 `--pdf` 查页码/裁图；加 `--ingest` 开溯源闸门；`--txt`/`--docx`/`--html` 做同源校验 |
| `python3 -m ankicards build <deck> --out x.apkg` | 构建 apkg | 有图片题必须 `--pdf`；引用 pages/docx/txt/web 定位必须 `--ingest` |
| `python3 -m ankicards preview <deck> --out x.html` | 单文件 HTML 预览 | 与 build 相同的闸门 |
| `python3 -m ankicards verify x.apkg` | 解包做结构审计 | 不需要源数据；`--json` 输出机器可读结果 |

**退出码**：

- `0` 成功。
- `1` 数据/闸门失败（schema 错误、未过 `--ingest`、verify 结构错误、`import --strict` 命中 error 级内容问题、`plan check` 有 error）。
- `2` 用法/环境错误（缺必填参数、坏 JSON、PDF/DOCX/TXT/HTML 不可读或编码错误、URL 被 SSRF/大小/超时限制拒绝、有图片题却缺 `--pdf`、apkg 不是 zip）。

`check`/`verify` 全绿只证明结构正确，不证明事实正确。

## 牌组目录与契约

```
<deck>/
  import-report.json  # import/plan compile 生成：卡片数 / 未出卡理由 / 内容规则命中（不参与构建）
  deck.json        # 可选：{"name": "顶层牌组名", "source_kind": "pdf"}
  cards/*.json     # 必需：{"deck": "子牌组名", "cards": [...]}
  crops.json       # 可选：图片题的 page + rect
  plan.json        # 可选：抽取中间产物（逐字 quote + 未出卡理由）；load_spec 不读它
```

字段定义以 `ankicards/schema.py` 为唯一真值；这里不复制字段表，避免文档与代码漂移。新增字段先改代码与测试，再写文档。

定位语义：

- `pages` 只表示 PDF 页码；`source_kind=md/txt/docx/web/image` 时写 `pages` 会报错；`unknown` 兼容放行但会给 warning。
- `source` 用于非 PDF 溯源；`source_kind=docx` 时必须匹配 `para:N` 或 `table:T/rR`，`source_kind=txt` 时必须匹配 `line:N`，`source_kind=web` 时必须匹配 `block:N`，且能在 ingest 产物中找到、文本非空。
- `pages` 和 `source` 可以并存：前者出截图，后者给段落级定位。

## 依赖与相关文件

- `ankicards/`：CLI 与校验/构建逻辑，skill 的外部依赖。
- `requirements.txt`：`genanki`、`python-docx`、`lxml` 等核心依赖。
- `requirements-render.txt`：PyMuPDF，仅 PDF 截图/裁图需要。
- `ankicards/schema.py`：卡片字段与定位契约的唯一真值。
- `README.md`：安装、工具链与数据说明。
- `docs/extraction-policy.md`：文档形态判定、禁止事项、已知失败模式与交付抽样规则。
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
| `unknown` 牌组带 `para:N`/`line:N`/`block:N` 却过不了 build | 声明 `source_kind=docx/txt/web` 并提供 `--ingest`；unknown 不再绕过定位闸门 |
| TXT 解码失败 | 默认 UTF-8；旧文件用 `--encoding gb18030`，或先转存 UTF-8 |
| 网页被拒绝 | 默认拒绝 localhost/内网；只支持静态 HTML，不执行 JS/登录；受 5 MB、20 秒、5 次 redirect 限制 |
| 网页一张卡都没解析出来 | 需要 h1-h6 标题 + `1. **关键词**：解释` 的段落/列表项；表格行不自动出题 |
| URL 出卡后 source 对不上 | 先用 `ingest` 生成 manifest，再 `import manifest.json --adapter web-points`，不要重新抓页面 |
| `verify` 报父卡组缺失 | warning：Anki 导入时会自动创建父卡组 |
| `verify` 报 markdown 转义残留 | 字段里有 `\<`、`\>` 之类未转义残留，修数据 |
| 散文走了 `txt-points`，出来“什么是环境准备？”“什么是第一步？” | 适配器把编号点当概念；这类输入不该进适配器。改走 `ingest` + 逐条写卡，见 §文档形态判定 |
| `--ingest` 报 sha256 不一致 | 清单不是这份源文件的产物；用同一份文件重跑 `ingest`，不要拿旧清单硬套 |
| 卡片答案在“；”处没了下半句 | 单行切点把续行丢了；用 `import --ingest` 按组出卡，或改走逐条写卡 |
| 答案只有“见第 4 节。” | 交叉引用被当成正文；这类段落应记为未覆盖，不要生成卡片 |

## 交付前验收

- `check` 0 error，且每条 warning 都能解释。
- `build` 成功，`verify` 0 error。
- 真机/Anki 导入一次：媒体 `Missing files: 0`。
- 连续两次构建，deck ID 与 guid 集合完全一致。
- 事实校对基准（hash 或 commit）已记录，并记下 ingest 产物的 `source_sha256`。
- 抽样自答：随机抽 10 张，遮住背面、只看正面自答，记录「答对 / 答不出 / 答错」。答不出说明卡面不可背，答错说明抽错了知识点——两者都退回改卡；不要只统计通过率。
- 散文/手册类：每张卡都能指回原文的具体一句或一段，而不是“读完整篇后总结的”。

## 公开数据与发布

- 公开材料放 `data/Android/`、`data/MQTT/`，便于他人复现。
- 非公开材料只放本地私有目录，加入本机 `.git/info/exclude`；只在本机构建，不入库、不发布。
- 含内页截图的 `.apkg` 和预览 HTML 同样按机密处理。
