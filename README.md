# Anki 卡组生成器

> 多领域知识 Anki 卡片生成 — Android 面试 1270 张 + MQTT 协议 200 张 + 江诗丹顿 2023 培训手册 273 张（含图片题）。工具链：`python3 -m ankicards check|build|verify`。

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
| Android面试::综合 | 666 张 |
| Android面试::Kotlin | 199 张 |
| Android面试::Java | 196 张 |
| Android面试::高频题集 | 125 张 |
| Android面试::阿里巴巴真题 | 84 张 |
| **总计** | **1270 张** |

### 江诗丹顿 2023 培训手册卡组

`output/江诗丹顿2023培训手册.apkg` —— **273 张卡片**（填空卡拆分为 299 张复习卡），从 141 页带图文的内部培训手册中提取，每张卡片背面都附原文页面截图，另有 27 张腕表产品图用于“看图识系列/识表款”。

| 子牌组 | 张数 | 内容 |
|------|------|------|
| 01 品牌与定位 | 28 | 宣传语、产量数据、座右铭、品牌平台、DNA、关键词、使命、合作 |
| 02 制表传奇 | 46 | 关键日期、马耳他十字、1755 年以来的杰出创作、年度主题 |
| 03 精湛工艺 | 37 | 打磨装饰、日内瓦印记与认证对比、艺术大师工艺、制表师职涯 |
| 04 系列·核心系列 | 49 | 系列金字塔、上市时间、产品术语；Patrimony／Traditionnelle／Fiftysix／Overseas／Égérie |
| 05 系列·特色与阁楼工匠 | 48 | Historiques／Malte／Heures Créatives／Métiers d'Art／Les Cabinotiers |
| 06 机芯 | 22 | 复杂功能四层分类、商用机芯、非凡机芯、57260 与 2756 等 |
| 07 钻石 | 10 | 钻石标准、火焰式切割 |
| 08 售后与保养 | 17 | 调校与上链、保养周期、服务类型、保修、官方文件 |
| 09 合规与资源 | 15 | CITES／RJC／金伯利进程、学习资源、客户体验名言 |

卡片类型：问答卡（正面问题，背面答案＋原文页截图）、填空卡（数字/年份/规格）、图片题（正面腕表照片，背面系列/型号与年代）。

预览：`output/江诗丹顿2023培训手册_预览.html`（单文件，双击即可浏览全部卡片与配图）。

> **导入提示**：用微信／QQ 传输 `.apkg` 时，部分版本会把文件改名为 `apk.1`、`apk.2` 之类，AnkiDroid 会提示“这不是一个有效的 Anki 卡组文件”。把后缀改回 `.apkg` 即可导入，或用数据线／网盘传输。
> 手机空间紧张时可在构建时加 `--lite`（不含原文页截图，约 1 MB）。

> **关于仓库内容**：该手册为品牌内部机密培训资料（页脚标注「专有机密资料——仅供内部培训使用」），因此本仓库只提交生成器、`cards/*.json` 卡片数据与裁剪配置，**原版 PDF、成品 `.apkg` 与 HTML 预览均不提交**，需在本地用 `python3 -m ankicards build data/江斯丹顿 --pdf <手册.pdf> --out <输出.apkg>` 生成。

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
# 1) 文本型 PDF → 逐页文本（默认写 .work/ingest/，被 gitignore；带 source_sha256）
python3 -m ankicards ingest <手册.pdf>

# 2) 校验卡片数据；--ingest 启用溯源闸门（页码必须存在且有文本）
python3 -m ankicards check  <牌组目录> [--pdf 手册.pdf] [--ingest .work/ingest/xxx.json]

# 3) 构建 apkg：引用 PDF 页码的牌组**必须**给 --ingest；有图片题时还必须给 --pdf
python3 -m ankicards build  <牌组目录> --out output/xxx.apkg --ingest .work/ingest/xxx.json \
                            [--pdf 手册.pdf] [--lite]

# 4) 预览同样过闸门；5) 导出后结构审计
python3 -m ankicards preview <牌组目录> --out x.html --ingest .work/ingest/xxx.json [--pdf 手册.pdf]
python3 -m ankicards verify output/xxx.apkg
```

退出码：

| 码 | 含义 | 典型场景 |
|---|---|---|
| `0` | 成功 | — |
| `1` | 数据/闸门失败 | schema 校验不通过、含 pages/DOCX 定位却未给 `--ingest`、verify 结构错误 |
| `2` | 用法或环境错误 | 缺必填参数、源目录为空、拒绝覆盖、坏 JSON、PDF 不可读/加密、缺 `--pdf` 却有图片题、apkg 不是 zip |

坏 JSON、加密 PDF、缺 `--pdf` 这类问题会以可读文案 + exit 2 结束，不再抛 traceback。

构建与预览对**含 pages 或 DOCX 定位的牌组强制要求 `--ingest`**：没有 ingest 产物就无法证明页码/段落真实存在，宁可拒绝也不产出假溯源。
同时给 `--pdf`/`--docx` 与 `--ingest` 时会比对 `source_sha256`；不是同一份文件直接 exit 2。

**格式支持矩阵（v0.2）**（明确的能力边界，避免“看起来支持”）：

| 输入 | 状态 | 说明 |
|---|---|---|
| 文本型 PDF | ✅ `ingest` | 逐页文本 + 页码引用；加密/损坏/扫描件直接 exit 2 |
| MD 题库 | ✅ `import --adapter android-md / mqtt-md` | 结构化问答格式 |
| 卡片 JSON | ✅ `check/build/verify` | 手工/agent 提炼后的事实来源 |
| DOCX | ✅ `ingest` + `import --adapter docx-points` | 逐段落/表格行文本 + `para:N`/`table:T/rR` 定位；忽略页眉页脚/图片/批注；不读取 Word 自动编号（`numPr`） |
| 扫描版 PDF | ❌ 明确拒绝 | 无文本层；本工具不含 OCR；空页 ≥50% 时 ingest 直接拒绝 |
| 可修复的损坏 PDF | ⚠️ 默认拒绝 | `--allow-repaired` 显式放行；文本可能缺失 |
| TXT | ⏸ 未注册适配器 | 缺“答案从哪来”的确定性来源，暂不做 |

DOCX 摄取限制：压缩包 ≤20 MB、解压后 ≤200 MB、块数 ≤5000（`--max-blocks` 可放宽）；
只读 body 段落与表格行，忽略页眉页脚、图片、批注；不读取 Word 自动编号（`numPr`）。
`docx-points` 只在首行“首格 + 第二格”都像表头时跳过（如 `概念 | 解释`），
`端口 | 解释` 会保留为数据，避免误删真实行。

依赖：`requirements.txt`（genanki + python-docx，必需）；`requirements-render.txt`（PyMuPDF，仅渲染 PDF 页面/裁图/带图预览时需要）。

牌组目录的契约：

```
<deck>/
  deck.json        # 可选：{"name": "顶层牌组名", "source_kind": "pdf"}
  cards/*.json     # 必需：{"deck": "子牌组名", "cards": [...]}
  crops.json       # 可选：图片题的裁图区域（page + rect）
```

字段定义以 `ankicards/schema.py` 为唯一真值；`skills/anki-card-builder/SKILL.md`
记录的是流程与判断（怎么选路径、怎么裁图、怎么校对），不复制字段表。

定位语义（**唯一真值**）：
- `pages` 只表示 **PDF 页码**，用于背面截图与裁图；`source_kind` 为 `md/txt/docx/image` 时写 `pages` 会报错；未声明（`unknown`）时兼容放行，但整副牌组只给 1 条 warning。
- `source` 用于非 PDF 来源的溯源；`source_kind=docx` 时必须是 `para:N`（body 内第 N 个段落，空段落也计数）或 `table:T/rR`（第 T 个表格第 R 行），且能在 ingest 产物中找到、文本非空。MD/TXT 仍用自由文本。
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
| `data/江斯丹顿/` | 品牌内部培训手册（PDF + cards + crops） | ❌ 机密，已被 .gitignore 排除，仅本机构建 |
| `.work/ingest/` | PDF 逐页 / DOCX 逐段文本产物 | ❌ 被 gitignore；含全文，不得入库 |
| `output/*.apkg` | 构建产物 | 视内容而定；含内部页截图的不要入库 |

### 适配器（原始资料 → cards/*.json）

非 JSON 的原始资料先过适配器，再走同一套 `check → build → verify`：

```bash
python3 -m ankicards import --list
python3 -m ankicards import data/Android --adapter android-md --out /tmp/android-deck --name "Android面试"
python3 -m ankicards build  /tmp/android-deck --out output/Android面试卡组.apkg

# DOCX：先摄取定位，再用 docx-points 生成卡片，最后带同源校验过闸门
python3 -m ankicards ingest 笔记.docx
python3 -m ankicards import 笔记.docx --adapter docx-points --out /tmp/docx-deck
python3 -m ankicards check  /tmp/docx-deck --docx 笔记.docx --ingest .work/ingest/笔记-<sha8>.json
```

| 适配器 | 输入 | 说明 |
|------|------|------|
| `android-md` | MD 题库目录 | 复用 `src/parsers` + 质量过滤 + 去重；实测重建 1270 张、5 个子牌组，与已入库卡组一致 |
| `mqtt-md` | MQTT 知识点 MD | 每个知识点生成一问一答 + 一道四选一；**源数据 `data3_mqtt/` 当前不在仓库，需要自备** |
| `docx-points` | 单个 DOCX | 标题→子牌组；`1. **关键词**：解释` 段落、至少两列的表格行→问答；`source` 写 `para:N`/`table:T/rR`；自动编号（`numPr`）不读取，会提示改为手写编号；首行只有“首格+第二格都像表头”时才跳过 |

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
│   ├── adapters.py          #   MD/TXT → 卡片数据（android-md / mqtt-md）
│   └── cli.py               #   check / build / verify / preview / import
├── skills/anki-card-builder/# 流程与判断（agent skill）
├── tests/                   # 数据契约与确定性 ID 的回归测试
├── src/                     # 解析器与处理逻辑（供适配器复用）
├── data/Android/            # 公开题库（MD）
├── data/江斯丹顿/           # 机密手册（不入库，仅本机构建）
├── output/                  # 生成的 .apkg
├── requirements.txt
└── AGENTS.md / docs/agents/ # 仓库协作约定
```

### 贡献新题库

- **内容型资料（手册、讲义）**：写 `cards/*.json`，跑 `check → build → verify`。
- **结构化题库（MD/TXT）**：先让解析器产出同样的 `DeckSpec`，再复用同一个构建入口；
  需要新增格式时加一个解析函数，而不是复制一份打包逻辑。
- **需要真实相机/PDF 才能复现的牌组**：同时加一份合成 fixture，否则 CI 无法回归。
- **新格式**：写一个适配器（`@register`）产出 `DeckData`，禁止再新增一个独立生成脚本。

### CI/CD

push master → GitHub Actions 自动上传 .apkg 到 Release。

## License

MIT
