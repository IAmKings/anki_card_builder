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

`output/江诗丹顿2023培训手册.apkg` —— **272 张卡片**（填空卡拆分为 298 张复习卡），从 141 页带图文的内部培训手册中提取，每张卡片背面都附原文页面截图，另有 26 张腕表产品图用于“看图识系列/识表款”。

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
> 手机空间紧张时可用 `python3 generate_vc.py --lite` 生成轻量版（不含原文页截图，约 1 MB）。

> **关于仓库内容**：该手册为品牌内部机密培训资料（页脚标注「专有机密资料——仅供内部培训使用」），因此本仓库只提交生成器、`cards/*.json` 卡片数据与裁剪配置，**原版 PDF、成品 `.apkg` 与 HTML 预览均不提交**，需在本地用 `python3 generate_vc.py` 生成。

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

### API 配置（AI 选择题生成，可选）

花销型功能，默认关闭。需通过 `--ai` 显式启用。

创建 `.env` 文件（已 gitignore，不会提交）：

```
DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxx   # 推荐，成本极低
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxx  # 备选
```

优先级：DeepSeek > Anthropic。

### 工具链（ankicards）

新牌组统一走一个入口，不再为每份文档写一个脚本：

```bash
# 校验卡片数据（不需要 genanki/PDF）
python3 -m ankicards check  <牌组目录> [--pdf 手册.pdf]

# 构建 apkg（有图片题时必须给 --pdf；--lite 不生成原文页截图）
python3 -m ankicards build  <牌组目录> --out output/xxx.apkg [--pdf 手册.pdf] [--lite]

# 导出后结构审计：媒体、HTML、guid、卡组层级、正面泄露
python3 -m ankicards verify output/xxx.apkg
```

依赖锁定在 `requirements.txt`（`genanki` 必需，`pymupdf` 仅在渲染时用到）。

牌组目录的契约：

```
<deck>/
  deck.json        # 可选：{"name": "顶层牌组名"}
  cards/*.json     # 必需：{"deck": "子牌组名", "cards": [...]}
  crops.json       # 可选：图片题的裁图区域（page + rect）
```

字段定义以 `ankicards/schema.py` 为唯一真值；`skills/anki-card-builder/SKILL.md`
记录的是流程与判断（怎么选路径、怎么裁图、怎么校对），不复制字段表。

确定性约定（改动前务必读 `ankicards/ids.py`）：
- deck ID / model ID 由牌组名 hash 得到，**同一名字永远是同一个 ID**，已发布牌组不要改名；
- 卡片 guid 由「牌组 + 正面 + 背面」决定，重复构建不会产生重复卡片；
- 媒体名统一为 `<deck-slug>-p<页码>.jpg` / `<deck-slug>-<裁图名>.jpg`，扁平、无中文。

### 数据与发布

| 目录 | 性质 | 是否入库 |
|---|---|---|
| `data/Android/` | 公开面试题库（MD） | ✅ 可入库，供他人复现构建 |
| `data/江斯丹顿/` | 品牌内部培训手册（PDF + cards + crops） | ❌ 机密，已被 .gitignore 排除，仅本机构建 |
| `output/*.apkg` | 构建产物 | 视内容而定；含内部页截图的不要入库 |

### 旧流水线（Android 面试卡组）

`main.py` + `src/` 是历史上的 MD/PDF 解析流水线，仍在维护但不再是新牌组的推荐路径：

```bash
pip3 install -r requirements.txt && pip3 install pymupdf4llm
python3 main.py          # 输出 output/Android面试卡组.apkg
```

### 项目结构

```
├── ankicards/               # 卡组工具链：schema / ids / build / verify / cli
├── skills/anki-card-builder/# 流程与判断（agent skill）
├── tests/                   # 数据契约与确定性 ID 的回归测试
├── main.py                  # 旧流水线入口（Android 面试卡组）
├── generate_mqtt.py         # MQTT 协议卡组（旧式独立脚本）
├── src/                     # 旧流水线的解析/处理/导出
├── data/Android/            # 公开题库（MD）
├── data/江斯丹顿/           # 机密手册（不入库）
├── output/                  # 生成的 .apkg
├── requirements.txt
└── AGENTS.md / docs/agents/ # 仓库协作约定
```

### 贡献新题库

- **内容型资料（手册、讲义）**：写 `cards/*.json`，跑 `check → build → verify`。
- **结构化题库（MD/TXT）**：先让解析器产出同样的 `DeckSpec`，再复用同一个构建入口；
  需要新增格式时加一个解析函数，而不是复制一份打包逻辑。
- **需要真实相机/PDF 才能复现的牌组**：同时加一份合成 fixture，否则 CI 无法回归。

### CI/CD

push master → GitHub Actions 自动上传 .apkg 到 Release。

## License

MIT
