# Changelog

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
