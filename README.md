![Anki 卡组制造器宣传图：把知识，做成记忆。](assets/anki-card-builder-promo.png)

# Anki 卡组生成器

> 多领域知识 Anki 卡片生成 — Android 面试 2305 张（1270 知识 + 326 填空 + 651 选择 + 58 对比）+ MQTT 协议 308 张（200 知识 + 30 填空 + 78 选择）。
> 工具链：`ingest → 可卡性预检 → plan（逐字 quote）→ compile → check → build → verify`。

## 0.4.0 有什么

这一版把「文档抽卡」做成了可审计的链路：机器只负责可判定的事实，判断落在 `plan.json` 上，
再由确定性校验与编译把它变成卡片。

- **plan 抽取契约**：每张卡带逐字 `quote`；`plan check` 校验引用、数字、定位、理由、覆盖率、
  密度、跨格式一致性与剧透，`plan compile` 才写卡。agent 不再直接写 `cards/*.json`。
- **续行与子项归并**：ingest 产出 `groups`，区间定位（`line:6-7`、`para:N-M`）成为合法来源；
  `import --ingest` 按组出卡，不再把续行丢在答案外。
- **PDF 跨页**：一段话被页码切断时写 `page:N-M`，卡片背面同时显示两页截图；ingest 的
  `page_spans` 会列出疑似续页对。
- **EPUB**：`chapter:C/p:M` 定位，支持小说/散文/随笔的 `--profile novel|essay`（长引用上限、
  防剧透、未出卡理由枚举都随 profile 变化）。
- **卡型**：`claim` / `style` / `phrase` / `fact` / `procedure`，每类有各自的验收标准。
- **密度与配额**：`--density {manual,novel,essay}` 按「读过的原文字数 / 卡数」检查疏密；
  手册口径下 `fact` + `procedure` 合并占比不足 30% 会提示。
- **跨格式与增量**：`--also` 拿每张卡的 quote 去另一种格式里逐字重找；`--incremental` 只把新卡
  并进已发布牌组，`retired` 显式下架，其余旧卡原样保留。
- **可卡性预检**：`scripts/precheck.py` 先算编号点/数字句/段长，PDF 按行拆，决定走适配器还是 plan。
- **数字等价**：`三天` 与 `3 天` 按数值比对，写法不同只提示；值不同照旧报错。

## 0.4.1 追加：从牌组派生填空与选择题

第一轮抽取出卡片之后，可以再读一遍**牌组本身**，把已有的问答改造成填空题与选择题：

```bash
python3 -m ankicards derive plan --deck dist/Android面试 --out plan_derive.json --seed 20261111
python3 -m ankicards derive check plan_derive.json --deck dist/Android面试
python3 -m ankicards derive compile plan_derive.json --deck dist/Android面试 --out dist/Android-派生
```

源牌组只读；正确项与挖空都是源答案里的逐字片段，代码块/模板/压平表格整卡跳过。
细节与参数见下文「派生题：填空题与选择题」。

私人资料（手册、培训讲义）可以再加一层严格模式：正确项必须锚定题干里的数字/专名，
多问号、PDF 碎片流、纯数字掩码直接跳过——产量低、正确率高，默认关闭，不影响公共牌组。

```bash
python3 -m ankicards derive plan --deck "data/江斯丹顿" --strict --out plan_derive.json
```

## 快速开始

### 1. 下载卡组

前往 [Releases](../../releases) 页面，下载最新的 `Android.apkg` 或 `MQTT.apkg`。

> **从 v0.3.2 升级到 0.4.0**：guid、模型与牌组 id 均未变化，可直接导入覆盖更新（Anki 按 guid 更新，
> 不会产生重复卡片）。新增的 plan/quote 只影响抽取流程，不影响已发布的卡片身份。
>
> **从 v0.3.0/v0.3.1 升级（v0.3.2 起）**：那一版的模型、guid 与牌组 id 都已变化，**不能覆盖升级**。
> 请先导出备份，在 Anki 中删除旧根牌组 `Android面试` 与 `MQTT协议`（含子牌组），再导入新包；
> 直接覆盖会产生重复卡片。

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
| Android面试::综合 | 666 张 |
| Android面试::Kotlin | 199 张 |
| Android面试::Java | 196 张 |
| Android面试::高频题集 | 125 张 |
| Android面试::阿里巴巴真题 | 84 张 |
| Android面试::填空 | 326 张 |
| Android面试::选择题 | 651 张 |
| Android面试::对比题 | 58 张 |
| **总计** | **2305 张** |

### 导入提示

用微信／QQ 传输 `.apkg` 时，部分版本会把文件改名为 `apk.1`、`apk.2` 之类，AnkiDroid 会提示“这不是一个有效的 Anki 卡组文件”。把后缀改回 `.apkg` 即可导入，或用数据线／网盘传输。

## 内容覆盖

| 领域 | 内容 |
|------|------|
| **Java** | JVM、GC、集合框架、并发编程、泛型、反射、异常处理 |
| **Kotlin** | 协程底层（CPS/状态机/调度器/Flow/Channel）、基础语法、高级特性 |
| **Android** | 四大组件、View 绘制、Handler 消息机制、IPC/Binder、Jetpack |
| **Compose** | 状态管理、副作用 API、Modifier、性能优化 |
| **Flutter** | Dart 语言基础、Widget 体系、状态管理 |
| **网络** | HTTP/HTTPS、TCP/UDP、WebSocket、DNS、状态码 |
| **算法** | 排序、二叉树、链表、栈/队列、动态规划、哈希表 |
| **设计模式** | 单例、工厂、观察者、代理、策略、建造者等 |
| **架构与性能** | MVC/MVP/MVVM、启动优化、内存管理、渲染优化、包体积 |

## 卡片类型

- **基础问答**：正面问题 → 背面答案，适合概念记忆
- **Cloze 填空**：隐藏关键词，适合关键术语和数值
- **代码块**：暗色背景 + 等宽字体渲染，适合代码演示
- **对比表格**：`<table>` 格式，适合横向对比知识点

## 源文件

| 文件 | 卡片数 |
|------|--------|
| Compose基础100问 | 93 |
| Android 基础100问 | 95 |
| Java经典100问 | 96 |
| Flutter基础100问 | 99 |
| Kotlin经典100问 | 99 |
| 网络协议基础100题 | 99 |
| 算法基础100题 | 100 |
| Android 与 Java 核心知识点 | 100 |
| 设计模式经典100 | 100 |
| 阿里巴巴Android面试题集 | 84 |
| Kotlin 协程深入 100 题 | 100 |
| 客户端架构设计50问 | 50 |
| 高频核心面试题（5部分） | 125 |
| 客户端性能优化30例 | 30 |

## 开发者

### 工具链（ankicards）

新牌组统一走一个入口，不再为每份文档写一个脚本：

```bash
# 1) 源 → 可寻址文本（PDF/DOCX/TXT/HTML/URL；默认写 .work/ingest/，被 gitignore）
python3 -m ankicards ingest <手册.pdf|笔记.docx|笔记.txt|book.epub|page.html|https://...>
# MOBI/AZW 不支持：先用 Calibre ebook-convert 转成 EPUB，再走上面这条

# 1.5) 可卡性预检：行级结构指标决定选路，页级版面指标只看跨页风险（只读，不写文件）
python3 scripts/precheck.py --ingest .work/ingest/xxx.json [--json]

# 1.6) 语义地图（可选，不进 CI）：单文档内的邻居/簇/近重复，只出报告
pip install -r requirements-rag.txt
python3 scripts/semantic_map.py --deck <牌组目录> --model ~/models/bge-small-zh

# 2) 文档抽取：agent/人只写 plan.json（每条带逐字 quote），先校验再编译
python3 -m ankicards plan check   plan.json --ingest .work/ingest/xxx.json --min-coverage 0.9 [--profile novel|essay] [--density essay] [--also 另一格式.json]
python3 -m ankicards plan compile plan.json --out <牌组目录> --ingest .work/ingest/xxx.json [--with-key] [--profile novel|essay] [--density essay] [--incremental]
python3 -m ankicards plan diff    plan.json --deck <牌组目录>
python3 -m ankicards derive plan    --deck <牌组目录> --out plan_derive.json [--ingest <清单>] [--options 4] [--dry-run]
python3 -m ankicards derive check   plan_derive.json --deck <牌组目录>
python3 -m ankicards derive compile plan_derive.json --deck <牌组目录> --out dist/<牌组>-派生

# 3) 校验卡片数据；--ingest 启用溯源闸门（页码/定位必须存在且有文本）
python3 -m ankicards check  <牌组目录> [--pdf 手册.pdf|--html page.html] [--ingest .work/ingest/xxx.json]

# 4) 构建 apkg：引用 pages/DOCX/TXT/Web 定位的牌组**必须**给 --ingest；有图片题时还必须给 --pdf
python3 -m ankicards build  <牌组目录> --out output/xxx.apkg --ingest .work/ingest/xxx.json \
                            [--pdf 手册.pdf|--html page.html] [--lite]

# 5) 预览同样过闸门；6) 导出后结构审计
python3 -m ankicards preview <牌组目录> --out x.html --ingest .work/ingest/xxx.json [--pdf 手册.pdf|--html page.html]
python3 -m ankicards verify output/xxx.apkg
```

### Agent 一条龙（复制即用）

```bash
python3 -m ankicards ingest 手册.pdf                      # → .work/ingest/*.json
python3 scripts/precheck.py --ingest .work/ingest/*.json   # 选路：adapter 还是 plan
# agent 只写 plan.json：每条卡片带逐字 quote，看过的段落记 skipped
python3 -m ankicards plan check   plan.json --ingest .work/ingest/*.json \
        [--profile manual|novel|essay] [--density manual|novel|essay] [--also 另一种格式.json]
python3 -m ankicards plan compile plan.json --out data/xxx --ingest .work/ingest/*.json [--with-key]
python3 -m ankicards check data/xxx --pdf 手册.pdf --ingest .work/ingest/*.json
python3 -m ankicards build data/xxx --pdf 手册.pdf --ingest .work/ingest/*.json --out dist/xxx.apkg
python3 -m ankicards verify dist/xxx.apkg
```

判断标准、卡型与密度口径见 `skills/anki-card-builder/SKILL.md`；失败模式、抽样规则与
预检阈值见 `docs/extraction-policy.md`；语义地图的安装、参数与输出契约见 `docs/semantic-map.md`。全部能力都在 CLI 里，没有隐藏入口；`python3 -m ankicards --version` 打印版本。

退出码：

| 码 | 含义 | 典型场景 |
|---|---|---|
| `0` | 成功 | — |
| `1` | 数据/闸门失败 | schema 校验不通过、含 pages/DOCX/TXT/Web/EPUB 定位却未给 `--ingest`、`plan check` 有 error、verify 结构错误 |
| `2` | 用法或环境错误 | 缺必填参数、源目录为空、拒绝覆盖、坏 JSON、PDF 不可读/加密、缺 `--pdf` 却有图片题、apkg 不是 zip |

坏 JSON、加密 PDF、缺 `--pdf` 这类问题会以可读文案 + exit 2 结束，不再抛 traceback。

构建与预览对**含 pages、DOCX/TXT/WEB 定位的牌组强制要求 `--ingest`**：没有 ingest 产物就无法证明页码/段落/行号/块号真实存在，宁可拒绝也不产出假溯源。

ingest 会同时产出 `groups`：编号点连同紧跟的缩进子项、没说完的续行、列表项归成一组，组区间（如 `line:3-7`）是合法定位。`import ... --ingest <清单>` 让 `*-points` 适配器按组出卡，答案并入组内其余文本、`source` 写区间；不传 `--ingest` 时仍按单行切点（旧行为）。
同时给 `--pdf`/`--docx`/`--txt`/`--html` 与 `--ingest` 时会比对 `source_sha256`；不是同一份文件直接 exit 2。URL 产物没有本地文件 sha，只做定位闸门，不再联网校验。

**格式支持矩阵（v0.4.0）**（明确的能力边界，避免“看起来支持”）：

| 输入 | 状态 | 说明 |
|---|---|---|
| 文本型 PDF | ✅ `ingest` | 逐页文本 + 页码引用；加密/损坏/扫描件直接 exit 2 |
| MD 题库 | ✅ `import --adapter android-md / mqtt-md` | 结构化问答格式 |
| 卡片 JSON | ✅ `check/build/verify` | 手工/agent 提炼后的事实来源 |
| DOCX | ✅ `ingest` + `import --adapter docx-points [--ingest]` | 逐段落/表格行文本 + `para:N`/`table:T/rR` 定位；忽略页眉页脚/图片/批注；不读取 Word 自动编号（`numPr`）；`--ingest` 按组合并续行/子项 |
| TXT | ✅ `ingest` + `import --adapter txt-points [--ingest]` | 物理行 `line:N`；标题 `# 标题` 或 `一、标题`，编号点 `1. **关键词**：解释`；默认 UTF-8（含 BOM），旧文件用 `--encoding gb18030`；`--ingest` 按组合并续行/子项 |
| Web（URL / 本地 HTML） | ✅ `ingest` + `import --adapter web-points [--ingest]` | 仅静态 HTML；提取标题/段落/列表项/表格行，`block:N` 定位；不执行 JS、不登录、不下载图片；URL 自动出卡用 manifest 两步；`--ingest` 把列表子项并进同组答案 |
| EPUB | ✅ `ingest` + `plan` | 按 OPF spine 顺序，`chapter:C/p:M` 定位；只收 XHTML/HTML，图片型/漫画无文本直接拒绝（不做 OCR）；支持 `--profile novel\|essay` |
| MOBI / AZW | ❌ 先转换 | 无 ingest 路径；用 Calibre `ebook-convert` 转成 EPUB 后再走上面这条（转换不进仓库） |
| 扫描版 PDF | ❌ 明确拒绝 | 无文本层；本工具不含 OCR；空页 ≥50% 时 ingest 直接拒绝 |
| 可修复的损坏 PDF | ⚠️ 默认拒绝 | `--allow-repaired` 显式放行；文本可能缺失 |

TXT 摄取限制：文件 ≤10 MB、行数 ≤50000（`--max-lines` 可放宽）；空行也计入 `line:N`。

Web 摄取限制：本地 HTML/URL 响应体 ≤5 MB、有效块 ≤5000、超时 20 秒、最多 5 次 redirect（`--max-bytes`/`--timeout` 可调）；只接受 `text/html`/`application/xhtml+xml`；默认拒绝 localhost/内网地址，确需抓本机页面加 `--allow-private-network`。

DOCX 摄取限制：压缩包 ≤20 MB、解压后 ≤200 MB、块数 ≤5000（`--max-blocks` 可放宽）；
只读 body 段落与表格行，忽略页眉页脚、图片、批注；不读取 Word 自动编号（`numPr`）。
`docx-points` 只在首行“首格 + 第二格”都像表头时跳过（如 `概念 | 解释`），
`端口 | 解释` 会保留为数据，避免误删真实行。

依赖：`requirements.txt`（genanki + python-docx + lxml，必需；lxml 也用于 HTML 解析）；`requirements-render.txt`（PyMuPDF，仅渲染 PDF 页面/裁图/带图预览时需要）。

牌组目录的契约：

```
<deck>/
  deck.json        # 可选：{"name": "顶层牌组名", "source_kind": "pdf"}
  cards/*.json     # 必需：{"deck": "子牌组名", "cards": [...]}
  crops.json       # 可选：图片题的裁图区域（page + rect）
  plan.json        # 可选：文档抽取的中间产物（每张卡的逐字 quote + 未出卡理由）
```

`plan.json` 是抽取环节的唯一接缝：机械适配器、人、离线 LLM 都只写它，
由 `plan check` 做确定性校验，再由 `plan compile` 编译成 `cards/*.json`。
它不在 `load_spec` 的读取范围内，所以放进牌组目录不会影响 `check`/`build`。
`quote` 不写进卡片（Anki 字段固定），plan 本身就是「这张卡从哪句话来」的审计记录。

`plan check` 校验的是可判定的事实，不判断卡片值不值得背：

| 校验 | 规则 |
|---|---|
| 引用 | `quote` 必须是定位文本的逐字子串（只忽略空白差异，标点必须一致） |
| 数字 | 答案里的每个数字都必须能在 `quote` 里找到（中文数字与阿拉伯数字按数值比对，「三天」=「3 天」，写法不同只提示）；问题里的数字只提醒 |
| 长度 | `quote` 8–300 字；`--profile novel`/`essay` 放宽到 800 字 |
| 定位 | 必须存在于 ingest 产物、文本非空、区间起点不大于终点 |
| 理由 | `skipped.reason` 必须属于枚举；`--profile` 决定可用语义理由 |
| 覆盖率 | 可选 `--min-coverage`，低于阈值报错 |
| 专名 | 卡面出现原文没有的英文标识符只提醒（可能是自造术语） |
| 卡型 | 见下表，按 `kind` 分别提醒 |

卡片可选 `kind` 标注卡型，`plan check` 按卡型给不同标准（缺省只提醒）：

| kind | 含义 | 按卡型检查 |
|---|---|---|
| `claim` | 观点/判断 | 问题建议写成问句（`？` 结尾） |
| `style` | 写法/结构/语气 | quote 建议 ≥30 字，太短看不出写法 |
| `phrase` | 金句 | quote 上限 60 字，太长背不下来 |
| `fact` | 事实/数字 | quote 里应有数字或日期，否则提醒 |
| `procedure` | 流程/步骤 | 问题应指向动作或对象（找谁 / 怎么做 / 要交什么） |

`plan compile` 会把卡型写成卡片标签 `kind:<kind>`（卡片字段不变）。

**增量编译**（`--incremental`）：写进一个已存在的牌组，而不是重建。plan 里出现的卡按 `key`
替换旧卡，`"retired": ["<key>", ...]` 里的卡下架，plan 没提到的旧卡原样保留。plan 里没写 key
时会用与 `--with-key` 相同的推导生成——前提是牌组名、定位、卡序都没变。它不自动对账：
Anki 侧删了卡，本地不会知道，要在 `retired` 里显式声明。

`--profile novel` 会额外做**防剧透**检查：卡面直接复制后文才出现的整句（六字以上连续片段）
会 warning；卡面提到后文才出场的拉丁名（如 Linda）会 warning；在 plan 里用
`"entities": [{"name": "林小姐", "locator": "chapter:3/p:1"}]` 声明的人物，若在登场前被提到就是
error。中文人名不猜，要精确检查就声明实体。

可选 `--also <另一份 ingest>`（可重复）做**跨格式交叉校验**：同一本书的 EPUB/PDF/TXT
定位体系不同（`chapter:C/p:M`、`page:N`、`line:N`），但正文应当一致。它会拿每张卡的
`quote` 去第二份里逐字重找，报告「交叉 pdf 88/88（跨单元 3）」。找不到说明两份文本不一致
或被格式改写；能命中但要跨单元拼接，说明该格式的定位无法单点溯源（PDF 换页）。

可选 `--density {manual,novel,essay}` 按口径检查密度：平均「读过的原文字数 / 卡数」落在
`manual` 200–700、`novel` 400–1200、`essay` 600–1600 之间；太密提示「可能在硬拆」，
太疏提示「可能漏了内容」。散文口径下出现 `fact` 卡、手册口径下 `fact` 占比低于 30%
也会提示。**密度只给 warning，不拦编译**——它是启发式，最终由人判断。

**同一段可以出多张卡**：只要两张卡的 `quote` 在原文里是不重叠的两句，就允许共用同一
定位；`quote` 重叠或完全相同才报错。同一段既出卡又记为未出卡只给 warning（确认不是
重复记账）。未出卡条目之间仍然互斥。

**PDF 跨页**：一段话被页码切断时，定位写 `page:N-M`（如 `page:190-191`），`quote` 可以
横跨两页；ingest 清单里的 `page_spans` 列出检测到的续页对（上一页未以句末标点收尾）。
`plan compile` 会把区间写成 `pages: [N, M]`，卡片背面同时显示这两页的截图。

字段定义以 `ankicards/schema.py` 为唯一真值；`skills/anki-card-builder/SKILL.md`
记录的是流程与判断（怎么选路径、怎么裁图、怎么校对），不复制字段表。
安装与依赖说明见 [`skills/README.md`](skills/README.md)。

### 模型候选：M3 协作流程

规则的干扰项只按长度和卡型挑，主题相关性差。需要更像“同类题”的选项时，把素材交给外部模型，
候选仍走同一套确定性校验：

```bash
# 1) 导出素材（不含答案以外的东西，不调用模型）
python3 -m ankicards derive packet --deck dist/Android面试 --out packet.json --limit 50

# 2) 模型按 packet 的 instructions/candidates_format 交回候选：
#    {"items":[{"source_key":"…","distractors":["…","…"]}]}

# 3) 并回 plan（原地更新；每题最多 2 条，超 5 个选项会被拒），然后人审
python3 -m ankicards derive merge plan_derive.json --deck dist/Android面试 --candidates candidates.json
python3 -m ankicards derive check plan_derive.json --deck dist/Android面试 --allow-model
```

要点：

- `merge` 只把候选标成 `origin: "model"` 并给卡片打 `review: true`，不替人判断对错。
- 每题默认上限 2 条模型候选；已有 4 个选项时只剩 1 个位置，想要 2 条就用 `derive plan --options 3`。
- `derive check` 对含模型候选的卡片出「需人工复审」提示；`derive compile` 必须显式加
  `--allow-model-distractors`，否则拒绝写盘。

### 复核页（可选）

编译前想快速扫一遍派生题，生成一张单文件 HTML：

```bash
python3 -m ankicards derive review plan_derive.json --deck dist/Android面试 --out review.html
```

浏览器直接打开，不联网、不上传。页面上可以按类型/可疑/关键词过滤，选择题会标出正确项与选项长度比，
填空题高亮挖空；每张卡可标「通过 / 可疑 / 错误」并写备注，标记存在浏览器 localStorage，点「导出标记」得到
`*-review-marks.json`，方便回头改 plan 或抽查。默认自带的可疑标记包括：选项长度比 >1.8、重复选项、
正确项过短、题干多个问号、只挖数字、挖空过短、引用过短等。

### 语义干扰项池（可选，M2）

`scripts/semantic_map.py` 会顺带写出 `seeds.json`（卡片的语义邻居）。把它交给 `derive`，
干扰项就能从「随机同牌组」换成「同一主题下的其他答案」：

```bash
python3 scripts/semantic_map.py --deck dist/Android面试 --model ~/models/bge-small-zh --out-dir .work/semantic
python3 -m ankicards derive plan --deck dist/Android面试 --seeds .work/semantic/seeds.json --out plan_derive.json
python3 -m ankicards derive merge plan_derive.json --deck dist/Android面试 --seeds .work/semantic/seeds.json
```

要点：

- 语义邻居只是「同主题」，**不代表它是错的**——同主题的另一个答案经常也成立。它是候选，不是干扰项。
- `merge` 会把改过的卡标 `review: true`，默认每题最多换 1 条；`--prefer-semantic` 才放开。
- `derive plan` 里 same-deck 够用时语义项不参与（兜底），只有同牌组不够时才补位。
- 语义项在 `check` 里记 `origin: "semantic"`，和 model 候选一样进入人审清单。

### 对比题候选（卡内条目，M2 后续）

跨卡邻居在真实牌组里多是「同一道题的不同问法」，不是对比项；真正能对比的是**一张卡答案里的并列条目**
（`强引用：… • 软引用：…`）。用脚本把它们挑出来：

```bash
python3 scripts/contrast_seeds.py --seeds .work/semantic/seeds.json --deck dist/Android面试 --out .work/semantic/contrast.json
```

输出 `contrast.json` / `contrast.md`：每对包含两个标签、原条目文字、以及建议问法
（「A」和「B」有什么区别？）。实测 Android 前 60 对里能直接用的如
`String` vs `StringBuffer`、`final` vs `finally`、`Application Context` vs `Activity Context`。

要点：

- 只产出候选，不写卡。对比题的答案要同时引用两条原文，需要多引用契约（未实现）。
- 默认 `--mode list`（卡内条目）；`--mode neighbor` 是跨卡邻居，实测多是近重复，适合合并/改写而不是对比。
- 抽象标签（「性能好」「概念」「优点」）会被过滤，不做对比题。

### 对比题编译（多引用契约）

对比题的答案同时引用两条原文，所以 `plan_derive.json` 新增了 `contrast` 类型，用 `sources` 记录多条引用：

```json
{"type": "contrast", "q": "「String」和「StringBuffer」有什么区别？",
 "a": "String：不可变…；StringBuffer：可变、线程安全…",
 "sources": [{"key": "…", "quote": "不可变…"}, {"key": "…", "quote": "可变、线程安全…"}]}
```

规则：

- `sources` 1–3 条，每条 `quote` 必须是该卡答案的**逐字子串**（忽略空白差异，HTML 标签清理留下的空格不算改写）；
- `a` 必须包含每一条 `quote`，否则视为「只写结论、没有引用」；
- 同一 `q + quotes` 只允许出现一次；
- 编译后落在独立分区「对比题」，卡片仍是 qa，标签 `derived:contrast` / `derived-from:<key>`。

```bash
python3 scripts/contrast_seeds.py --seeds .work/semantic/seeds.json --deck dist/Android面试 --out .work/semantic/contrast.json
python3 -m ankicards derive contrast .work/semantic/contrast.json --deck dist/Android面试 --out plan_contrast.json
python3 -m ankicards derive check plan_contrast.json --deck dist/Android面试
python3 -m ankicards derive compile plan_contrast.json --deck dist/Android面试 --out dist/Android-对比
```

实测 Android：1270 知识 + 326 填空 + 651 选择 + 58 对比；MQTT：200 知识 + 30 填空 + 78 选择，均通过 build 与 `verify`（结构检查通过，无重复 guid）。
- 模型交回的候选必须长度 2–60 字、不与正确项/已有选项重复，否则 merge 直接拒收并打印原因。
- 候选长度与正确项相差不要超过 50%（packet 里带 `correct_chars`）；`derive check` 发现选项
  最长/最短超过 2 倍时会给「长度可能泄漏答案」提示。
- 选项已满时加 `--replace-same-deck`：用模型候选替换长度最不匹配的同牌组干扰项，
  不碰正确项、也不替换 local 选项。
- 想要「1 正确 + 2 模型、零同牌组」：`derive plan --options 3` 后
  `merge --prefer-model`，模型候选一到就替换同牌组项，最终 3 个选项全是模型写的。

### 派生题：填空题与选择题

从**已写好**的牌组派生第二层卡，不重读原文。源牌组只读；派生结果先落 `plan_derive.json`，`derive check` 通过后再编译到独立目录。

- 填空题：从源答案里挑逐字片段（数字+单位、专名、术语，2–20 字）挖空，`source_excerpt` 必须能在源答案里逐字找到。
- 选择题：正确项是逐字片段（≤60 字）；干扰项优先同牌组其他卡的答案片段（`same-deck`），给了 `--ingest` 才补 `local`；模型写的干扰项要标 `origin:"model"`，单题 ≤2 个，编译需 `--allow-model-distractors`，且必须人工审。
- 参数：`--options 3–5`（默认 4）、`--max-option-chars`、`--cloze-max-span`、`--cloze-per-card 1|2`、`--distractor-source same-deck|local|hybrid|none`、`--seed` 控制选项顺序、`--cloze-limit` / `--choice-limit`。
- 背面自动附「來源：<源卡问题>」；`--show-source full` 显示全文，`off` 关闭。
- 工具只保证**可定位、可判分**（引用逐字、单正确项、选项不重复），不保证题目值得考；编译前用 `derive report` 抽读。

定位语义（**唯一真值**）：
- 可选 `key`：12 位小写十六进制（`plan compile --with-key` 生成）。有 key 的卡按 key 定 guid，改文字不会在 Anki 里变成新卡；只用于**新牌组**，已发布牌组不要加。
- `pages` 只表示 **PDF 页码**，用于背面截图与裁图；`source_kind` 为 `md/txt/docx/web/image` 时写 `pages` 会报错；未声明（`unknown`）时兼容放行，但整副牌组只给 1 条 warning。
- `source` 用于非 PDF 来源的溯源；`source_kind=docx` 时必须是 `para:N` 或区间 `para:N-M`（body 内第 N 个段落，空段落也计数），或 `table:T/rR`（第 T 个表格第 R 行）；`source_kind=txt` 时必须是 `line:N` 或 `line:N-M`（`splitlines()` 的物理行号，空行也计数）；`source_kind=web` 时必须是 `block:N` 或 `block:N-M`（提取后的有效块序号，空块不计数）；`source_kind=epub` 时必须是 `chapter:C/p:M`（spine 第 C 章第 M 个内容块）。三者都要求能在 ingest 产物中找到、文本非空，区间还要求起点不大于终点；MD 仍用自由文本。
- 两者可以并存：`pages` 出截图，`source` 给段落级定位。
- 卡片字段是**白名单**，未知字段直接报错，避免“校验通过但构建不消费”的假溯源。

确定性约定（改动前务必读 `ankicards/ids.py`）：
- deck ID / model ID 由牌组名 hash 得到，**同一名字永远是同一个 ID**，已发布牌组不要改名；
- 卡片 guid 由 `identity_seed(牌组名, 卡片)` 决定：qa = 问题+答案，cloze = 文本，image = 图片名+问题+答案（与查重身份同源）；同一份数据重复构建 guid 稳定。
  **注意**：身份算法变更会让重建的 note 变成新卡（Anki 里会新增而不是更新旧卡）——本项目不提供迁移工具，发布后请勿随意改身份规则；
- 媒体名统一为 `<deck-slug>-p<页码>.jpg` / `<deck-slug>-crop-<安全名>-<hash8>.jpg`，扁平、无中文。

### 数据与发布

| 目录 | 性质 | 是否入库 |
|---|---|---|
| `data/Android/` | 公开面试题库（MD） | ✅ 可入库，供他人复现构建 |
| `data/MQTT/` | 公开 MQTT 知识点（MD） | ✅ 可入库，供他人复现构建 |
| `data/员工手册/`、`data/一千七百種靠近/` | 公司内部手册 / 版权书（私人语料） | ❌ 已进 `.gitignore`；只在本机使用，不入库、不上传 |
| `.work/ingest/` | PDF 逐页 / DOCX 逐段 / TXT 逐行 / Web 逐块文本产物 | ❌ 被 gitignore；含全文，不得入库 |
| `output/*.apkg` | 构建产物 | 视内容而定；含内部页截图的不要入库 |

### 适配器（原始资料 → cards/*.json）

非 JSON 的原始资料先过适配器，再走同一套 `check → build → verify`：

```bash
python3 -m ankicards import --list
python3 -m ankicards import data/Android --adapter android-md --out /tmp/android-deck --name "Android面试"
python3 -m ankicards build  /tmp/android-deck --out output/Android面试卡组.apkg

python3 -m ankicards import data/MQTT --adapter mqtt-md --out /tmp/mqtt-deck --name "MQTT协议"
python3 -m ankicards build  /tmp/mqtt-deck --out output/MQTT协议卡组.apkg

# DOCX：先摄取定位，再用 docx-points 生成卡片，最后带同源校验过闸门
python3 -m ankicards ingest 笔记.docx
python3 -m ankicards import 笔记.docx --adapter docx-points --out /tmp/docx-deck
python3 -m ankicards check  /tmp/docx-deck --docx 笔记.docx --ingest .work/ingest/笔记-<sha8>.json

# TXT：物理行 line:N；默认 UTF-8，旧文件可指定编码
python3 -m ankicards ingest 笔记.txt --encoding utf-8-sig
python3 -m ankicards import 笔记.txt --adapter txt-points --out /tmp/txt-deck
python3 -m ankicards check  /tmp/txt-deck --txt 笔记.txt --ingest .work/ingest/笔记-<sha8>.json

# Web（本地 HTML）：提取块 + 生成卡片 + 同源校验
python3 -m ankicards ingest page.html
python3 -m ankicards import page.html --adapter web-points --out /tmp/web-deck
python3 -m ankicards check  /tmp/web-deck --html page.html --ingest .work/ingest/page-<sha8>.json

# Web（URL）：先抓取成 manifest，再从同一份 manifest 出卡，避免二次抓取
python3 -m ankicards ingest https://example.com/article
python3 -m ankicards import .work/ingest/example_com-article-<sha8>.json --adapter web-points --out /tmp/web-deck
python3 -m ankicards check  /tmp/web-deck --ingest .work/ingest/example_com-article-<sha8>.json
```

| 适配器 | 输入 | 说明 |
|------|------|------|
| `android-md` | MD 题库目录 | 复用 `src/parsers` + 质量过滤 + 去重；重建 2305 张（1270 知识 + 326 填空 + 651 选择 + 58 对比）、8 个子牌组；guid/模型/牌组身份由 `tests/golden/public_decks.json` 校验 |
| `mqtt-md` | MQTT 知识点 MD | 每个知识点生成一问一答 + 一道四选一；源数据在 `data/MQTT/`，可直接复现 |
| `docx-points` | 单个 DOCX | 标题→子牌组；`1. **关键词**：解释` 段落、至少两列的表格行→问答；`source` 写 `para:N`/`table:T/rR`；自动编号（`numPr`）不读取，会提示改为手写编号；首行只有“首格+第二格都像表头”时才跳过 |
| `txt-points` | 单个 TXT | 标题（`# 标题` / `一、标题`）→子牌组；`1. **关键词**：解释` 或 `1. 关键词：解释`→问答；`source` 写 `line:N`；只生成问答，不生成四选一 |
| `web-points` | 单个 HTML 或 web ingest JSON | 标题（h1-h6）→子牌组；编号段落/列表项→问答；`source` 写 `block:N`；表格行不自动出题；URL 先 ingest 再 import manifest |

新增一种格式 = 在 `ankicards/adapters.py` 里加一个带 `@register("名字")` 的函数，
产出 `DeckData`（含 `source_kind`），不需要再复制打包逻辑。`import` 会把
`{"name", "source_kind"}` 一并写进 `deck.json`，不再出现“每次 check 一条 unknown 警告”。

### 项目结构

```
├── ankicards/               # 卡组工具链
│   ├── schema.py            #   卡片数据契约（唯一真值）
│   ├── ids.py               #   确定性 deck/model ID
│   ├── build.py             #   打包（模型、媒体、lite）
│   ├── verify.py            #   导出后结构审计
│   ├── preview.py           #   单文件 HTML 预览
│   ├── ingest.py            #   PDF/DOCX/TXT/HTML/URL/EPUB → 可寻址文本清单（含 groups）
│   ├── epub.py              #   EPUB：OPF spine 顺序 + chapter:C/p:M 定位
│   ├── grouping.py          #   续行/子项归并成可整段取用的组
│   ├── precheck.py          #   可卡性预检（行级结构指标 + 页级版面指标）
│   ├── quality.py           #   确定性质量规则 Q1–Q9（答案过短/截断/交叉引用…）
│   ├── plan.py              #   plan.json 契约：E1–E8 校验、密度、跨格式、剧透、增量
│   ├── docx.py / txt.py / web.py  # 共享的段落/行/HTML 块提取
│   ├── adapters.py          #   MD/DOCX/TXT/Web → 卡片数据（android-md / mqtt-md / docx-points / txt-points / web-points）
│   └── cli.py               #   ingest / import / plan / check / build / verify / preview
├── skills/anki-card-builder/# 流程与判断（agent skill）
├── scripts/                 # precheck.py（可卡性预检）、可复现构建与 apkg 身份比对（发布 P0）
├── tests/                   # 数据契约、发布契约与身份回归测试
├── src/                     # 解析器与处理逻辑（供适配器复用）
├── data/Android/            # 公开题库（MD）
├── data/MQTT/               # 公开 MQTT 知识点（MD）
├── output/                  # 生成的 .apkg
├── requirements.txt
└── AGENTS.md / docs/agents/ # 仓库协作约定
```

### 贡献新题库

- **内容型资料（手册、讲义）**：写 `cards/*.json`，跑 `check → build → verify`。
- **结构化题库（MD/TXT/网页）**：先让解析器产出同样的 `DeckSpec`，再复用同一个构建入口；
  需要新增格式时加一个解析函数，而不是复制一份打包逻辑。
- **需要真实相机/PDF 才能复现的牌组**：同时加一份合成 fixture，否则 CI 无法回归。
- **新格式**：写一个适配器（`@register`）产出 `DeckData`，禁止再新增一个独立生成脚本。

### 发布与可复现构建（v0.4.6）

发布物不再直接上传仓库里某个历史时点的 `output/*.apkg`，而是由 tag 指向的源码重建：

```bash
# 重建 Android + MQTT，并用 golden 校验 guid/模型/牌组身份
python3 scripts/build_public_decks.py --out dist --check-golden

# 排查两个包为什么不兼容：打印 guid 交集、模型字段、模型/牌组 id
python3 scripts/apkg_identity.py old.apkg new.apkg
```

- `tests/golden/public_decks.json` 固定公开牌组身份；只有**有意**改变内容/模型/牌组时才用 `--write-golden` 更新，并在提交里说明原因。
- `.github/workflows/release.yml` 在 `v*` tag 上执行 `import → build → verify → --check-golden`，只上传 `dist/Android.apkg`、`dist/MQTT.apkg`。
- `.github/workflows/verify.yml` 的 `public-decks` job 在每次 push/PR 重建并校验同一份 golden。
- v0.3.2 的 P0 证据（旧包与 HEAD 重建的 0/1270、0/200 对比）见 [`docs/evidence/v0.3.2-release-identity.md`](docs/evidence/v0.3.2-release-identity.md)。
- 0.4.0 / 0.4.1 / 0.4.2 / 0.4.3 / 0.4.4 / 0.4.5 / 0.4.6 的变更清单与验证记录见 [`CHANGELOG.md`](CHANGELOG.md)。

### CI/CD

- push/PR → `Verify card decks`：单元测试、已入库 apkg 结构审计、公开牌组 identity 校验。
- push `v*` tag → `Release Anki APKG`：从 tag 源码重建、校验、上传两个 apkg；不再扫描 `output/` 全量上传。

## License

MIT
