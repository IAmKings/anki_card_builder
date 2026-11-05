# Anki 卡组生成器

> 多领域知识 Anki 卡片生成 — Android 面试 1270 张 + 山河集珠宝销售 + MQTT 协议 200 张 + 江诗丹顿 2023 培训手册 272 张（含图片题）。

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

### 独立卡组生成器

```bash
# MQTT 协议卡组（200 张：100 Q&A + 100 选择题）
python3 generate_mqtt.py              # 快速模式，不调 AI
python3 generate_mqtt.py --ai          # AI 生成选择题干扰项 + 扩展提示

# 山河集珠宝销售卡组
python3 generate_shanheji.py

# 江诗丹顿 2023 培训手册卡组（PDF → 卡片 + 页面截图 + 产品图）
python3 generate_vc.py            # 生成 apkg + HTML 预览
python3 generate_vc.py --check    # 只校验卡片数据（页码、图片、字段）
```

江诗丹顿卡组的数据源在 `data/江斯丹顿/`：`cards/*.json` 是卡片正文（每题带 `pages`
原文页码），`crops.json` 定义从 PDF 页面裁切产品图的区域，`generate_vc.py` 负责渲染
页面截图、裁图、生成 `.apkg` 与单文件 HTML 预览。加卡片只需编辑 `cards/*.json`。

### 从源码构建（Android 面试卡组）

```bash
# 安装依赖
pip3 install pymupdf4llm genanki

# 运行流水线
python3 main.py

# 输出：output/Android面试卡组.apkg
```

### 项目结构

```
├── main.py                  # 入口（~45行）
├── generate_mqtt.py         # MQTT 协议卡组生成器
├── generate_shanheji.py     # 山河集珠宝销售卡组生成器
├── generate_vc.py           # 江诗丹顿培训手册卡组生成器（PDF 取图 + genanki）
├── src/
│   ├── config.py            # 配置 + API Key 加载
│   ├── models.py            # 数据模型（Flashcard）
│   ├── utils.py             # 工具函数（转义、表格转换、内容清理）
│   ├── pipeline.py          # 流水线编排（Android 面试）
│   ├── ai_mc_generator.py   # 通用 AI 选择题生成模块
│   ├── parsers/             # 4种MD + 山河集 TXT 解析器
│   ├── processing/          # 质量过滤 + 去重
│   └── export/              # genanki .apkg 导出
├── data/                    # Android 面试题库（MD）
├── data2/山河集/            # 山河集珠宝销售题库（TXT）
├── data3_mqtt/              # MQTT 协议题库（MD）
├── data/江斯丹顿/           # 江诗丹顿培训手册 PDF + cards/*.json + crops.json
└── output/                  # 生成的 .apkg
```

### 贡献新题库

将 MD 文件放入 `data/` 目录，运行 `python3 main.py` 即可增量处理。

支持的 MD 格式：
| 格式 | 示例 | 答案标记 |
|------|------|----------|
| 粗体标题 | `### **1. 问题**` | `**答案**：` |
| 粗体编号 | `**1. 问题**` | `**确切答案：**` |
| 纯文本标题 | `### 1. 问题` | `**答：**` |
| 案例标题 | `### 案例 1：标题` | 内联 |

新卡片会自动去重合并。

### 开发新的领域卡组

1. 创建 `generate_xxx.py` 独立脚本
2. 导入共享 AI 模块：
```python
from src.ai_mc_generator import generate_mc_data

mc_data = generate_mc_data(
    points=[{"number": 1, "keyword": "...", "explanation": "..."}, ...],
    domain="领域名",
    api_key=CONFIG.deepseek_api_key or CONFIG.anthropic_api_key,
    api_model=...,
    api_provider="deepseek",
)
```
3. 用户调用 `python3 generate_xxx.py --ai` 启用 AI，一次配置多项目共用。

### CI/CD

push master → GitHub Actions 自动上传 .apkg 到 Release。

## License

MIT
