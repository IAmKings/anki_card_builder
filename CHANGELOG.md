# Changelog

## 0.4.4（2026-11-12）

对比题候选的质量修复：0.4.3 的 58 张里有「底层原理 vs 不推荐原因」「包含五大部分 vs 线程私有」这类
小标题对比，不是概念对比。本版收紧候选生成，并把对比题 key 改成内容稳定型。

### 修复

- 过滤元词标签（包含/分为/场景/原因/原理/优势/代码/示例/正解/姿势/开销…），并限制标签形状
  （不能以 `*`、`+`、数字开头）；
- 跳过代码/示例型答案的整张卡（`CODE_ANSWER` 识别 `public class`、`System.`、`=>` 等）；
- 同一标签对去重（忽略括号注释与空白），不再出现「继承 vs 接口」两遍；
- 对比题 key 由「源卡串 + 题干」派生，候选增删时保留下来的卡 guid 不漂移。

### 升级注意

- 若已导入 0.4.3 的 58 张对比题，**先删除 `Android面试::对比题` 子牌组再导入 0.4.4**，
  否则旧对比题会以新 guid 残留一份；原 1270 张卡不受影响。
- Android 仍为 1328 张（1270 + 58），但对比题的组成与 guid 已变化。

## 0.4.3（2026-11-12）

对比题正式并入 Android 发布牌组：卡内条目候选经 `derive contrast` 折成 58 张对比题，
作为 `Android面试::对比题` 子牌组，与原 1270 张卡同包发布。

### 新增

- `data/Android/contrast.json`：60 条卡内条目对比候选（确定性文本，不含模型输出）。
- `scripts/build_public_decks.py` 支持 `contrast` 字段：构建时自动生成对比题 plan、
  编译并追加为独立分区；Android 发布物从 1270 张变为 1328 张。
- `tests/golden/public_decks.json` 同步为 1328；`test_public_deck_identity` 断言更新。

### 说明

- 原 1270 张卡的 guid 不变，对比题新增 58 个 guid；导入后只多出 `Android面试::对比题`。
- 对比题依赖源卡 key，`data/Android/contrast.json` 与牌组名（Android面试）绑定；
  改牌组名需要重新生成候选。

## 0.4.2（2026-11-11）

把「模型写干扰项」接进派生链路：素材包交给外部模型，候选只并入 plan，再走确定性校验与人审。
工具本身仍不调用模型；公开牌组（Android / MQTT）身份不变。

### 新增

- **`derive packet`**：导出源卡的 `q / answer / correct / correct_chars`，附
  `candidates_format` 与提示词要求（长度与正确项相差 ≤50%），工具不联网、不调用模型。
- **`derive merge`**：读 `{"items":[{source_key,distractors}]}`，逐条过闸（2–60 字、
  不与正确项/已有选项重复或高度相似、每题最多 2 条、选项总数 ≤5）；通过的标
  `origin: "model"`，并给卡片打 `review: true`。
  - `--replace-same-deck`：选项已满时替换长度最不匹配的同牌组项，不碰正确项。
  - `--prefer-model`：候选一到就替换同牌组项，配合 `--options 3` 得到「1 正确 + 2 模型」。
- **选项长度提示**：`derive check` 发现最长/最短比 >2 时警告「长度可能泄漏答案」。
- **`docs/derive-packet.md`**：素材包结构、候选格式、模型提示词模板、人审清单。

### 变更

- `derive check` 的 stats 增加 `review` 计数；`derive report` 与 CLI 输出同步展示。

### 验证

- 413 tests OK（1 skipped），golden 通过（Android 1270 / MQTT 200）。
- 真实牌组：Android 10 题 × 2 条模型候选，`--prefer-model` 后替换 20 条同牌组项、
  每题 3 个选项（1 正确 + 2 模型）、同牌组残留 0；长度比提示从 338 张降到 195 张。
- 完整派生链：plan → merge → check --allow-model → compile → build → verify 通过。

## 0.4.1（2026-11-11）
## 0.4.1（2026-11-11）

在第一轮抽取出的牌组之上做**派生题**：读现有卡片的问题与答案，生成填空题与选择题。
源牌组只读，派生结果先落成一份可审的 `plan_derive.json`，检查通过才编译成独立牌组。
升级不涉及身份变化：Android.log / MQTT.apkg 的 guid、模型与牌组 id 与 0.4.0 相同。

### 新增

- **`derive` 子命令组**（`ankicards/derive.py`）：`plan` / `check` / `compile` / `report` / `packet`。
  - `plan`：按 `--seed` 确定性挑题；`--options 3–5`（默认 4）、`--max-option-chars`、
    `--cloze-per-card`、`--cloze-max-span`、`--distractor-source {same-deck,local,hybrid,none}`、
    `--section`、`--cloze-limit`/`--choice-limit`、`--show-source {short,full,off}`、`--dry-run`。
  - `check`：D1–D9 —— 挖空与正确项必须逐字来自源答案、选项唯一、无重复渲染体、
    干扰项来源合法、model 干扰项需要 `--allow-model-distractors`。
  - `compile`：写 `dist/<牌组>-派生/`，分区「填空」「选择题」；选择题渲染进 qa，不新增笔记类型；
    背面附「來源：<源卡问题>」（`--show-source short` 默认截断 80 字）。
  - `packet`：导出素材包给外部模型候选，工具本身不调用模型。
- 填空题取源答案的逐字片段，`{{c1::…}}` 只围绕片段；选择题正确项同样是逐字片段，
  不摘要、不改写。
- 干扰项优先级：同牌组（`same-deck`）→ 本地语料（给了 `--ingest` 才启用，选项须能在声明定位里找到）
  → 模型另写（`hybrid`，单题 ≤2、`origin:"model"`、必须人工审）。
- 两道确定性闸：代码块/模板占位/被压平的表格行整卡跳过（`code_snippet`）；
  挖空不得切在 token 中间（`30-40%`、`NetworkType.CONNECTED` 一律不出题）。

### 变更

- 新增 `--version` 输出（0.4.0 已在 0.4.1 之前提供，此处不重复）。

### 修复

- `plain()` 对双重转义 HTML 不幂等，导致 `source_q` 与片段校验对不上（`cards[1036]`）。
- 选择题最初写成 `type=choice` 被 schema 拒绝，改为渲染进 `qa`。

### 验证

- `python -m unittest discover -s tests`：404 passed, 1 skipped。
- `python3 scripts/build_public_decks.py --out dist --check-golden`：Android 1270 / MQTT 200，guid 不变。
- 真实牌组：Android 1270 张 → 填空 402 / 选择 651（`code_snippet` 733、`no_cloze_span` 754）；
  MQTT 200 张 → 填空 144 / 选择 178。派生包 `build` + `verify` 通过。

## 0.4.0（2026-11-11）

## 0.4.0（2026-11-11）

这一版把「文档 → 卡片」做成可审计链路：机器管可判定事实，判断落在 `plan.json` 上，
再由确定性校验与编译产出卡片。卡片身份（guid / deck id / model id）与 0.3.2 一致。

### 新增

- **plan 抽取契约**（`ankicards/plan.py`）：`plan.json` 记录每张卡的逐字 `quote`、
  可选的 `kind` / `key` / `entities`，以及看过的段落的 `skipped` 理由。
  `plan check` 校验 E1–E8（引用、数字、长度、定位、理由、覆盖率、专名、身份 key），
  `plan compile` 只在无 error 时写盘；`plan diff` 对比 plan 与现有牌组。
- **分组与区间定位**（`ankicards/grouping.py`、`ingest` 的 `groups`）：编号点连同缩进子项、
  续行、列表项归成一组，`line:6-7`、`para:N-M`、`page:N-M` 成为合法定位；
  `import --ingest` 按组出卡，答案并入组内其余文本。
- **PDF 跨页**：`page:N-M` 引用横跨两页，`plan compile` 写 `pages: [N, M]`，
  ingest 清单的 `page_spans` 列出疑似续页对。
- **EPUB**（`ankicards/epub.py`）：按 OPF spine 顺序提取，`chapter:C/p:M` 定位；
  图片型/漫画无文本时明确拒绝（不做 OCR）。MOBI/AZW 需先转 EPUB。
- **profile**：`--profile {manual,novel,essay}` 决定引用上限、可用理由与额外检查
  （novel 防剧透、essay 长引用与未出卡理由）。
- **卡型**：`claim` / `style` / `phrase` / `fact` / `procedure`，各带独立验收标准；
  `plan compile` 写成 `kind:<kind>` 标签。
- **密度与卡型配额**：`--density {manual,novel,essay}` 按「读过的原文字数 / 卡数」检查；
  手册口径下 `fact` + `procedure` 合并占比不足 30% 提示；只 warning，不拦编译。
- **跨格式交叉校验**：`plan check --also <另一份 ingest>` 把每张卡的 quote 拿到另一种格式里
  逐字重找，区分「找不到」与「跨单元拼接才命中」（PDF 换页属正常）。
- **增量编译**：`plan compile --incremental` 按 `key` 替换、按 `retired` 下架、其余旧卡保留；
  不自动对账（Anki 侧删除本地无从得知）。
- **`ankicards --version`**：打印当前版本，便于 agent 与 CI 判定工具链版本。
- **可卡性预检**：`scripts/precheck.py --ingest <清单>` 算编号点/数字句/段长/引号/表格行，
  PDF 先按行拆；页级指标单独输出，只提示跨页风险。
- **数字等价**：中文数字只解析「数字 + 单位」形态，`三天` 与 `3 天` 按数值比对通过并提示
  写法不同；裸序列不当数字；值不同仍报错。

### 变更

- `import` 新增 `--strict`（error 级内容问题直接失败且不写牌组）与 `--ingest`（按组合并、
  校验 `source_sha256`），并写 `import-report.json` 记录未出卡理由与内容规则命中。
- `plan check` 的 E5 从「条目区间不得相交」放宽为「同一段可以出多张卡，但 quote 不得重叠」。
- SKILL 增加「准入：先问用途」「卡型与密度」「可卡性预检」三节；README 增加 0.4.0 能力清单、
  EPUB/MOBI 格式矩阵与「Agent 一条龙」。

### 修复

- 适配器在 docx/txt/web 上静默丢弃续行与子项；改为记账（`blank` / `heading` / `not_point` /
  `continuation` / `table_header` / `duplicate_input`）并支持按组出卡。
- 手打长 quote 易漏字；`plan check` 给出「不是逐字子串」+ 定位，配合起止切片即可定位。
- E2 曾把问题里的编号（「案例 2」）当卡面数字；改为只校验答案，问题里的数字只提示。
- 密度分子曾用「卡片自己的定位文本」导致 90 字/张的假报；改为「条目实际覆盖到的原文」。

### 验证

- 单元测试 391 条通过（1 skip）；`build_public_decks.py --check-golden` 通过，
  Android 1270 / MQTT 200 的 guid 集合不变。
- 真实语料验收：200 页培训手册（PDF）、散文集三格式（EPUB/PDF/TXT）、两份员工手册（PDF）
  全部走 `plan check → compile → check → build → verify`；散文三格式 cross-check 88/88。
- 盲测：两份员工手册各抽 10 张，10/10 可由原文回答；散文集 10 张自答 9 对 / 1 半对。

## 0.3.2

- 发布物改为 tag 源码重建 + golden 身份校验（P0）；`--ingest` 溯源闸门上线。
- 详见 `docs/evidence/v0.3.2-release-identity.md`。
