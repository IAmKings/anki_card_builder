# 派生题素材包（derive packet）与模型候选

`derive packet` 导出一个 JSON，给外部模型（或人）挑干扰项；工具本身不调用模型。
模型只能写候选，不能写卡：候选经 `derive merge` 并回 plan，再走 `derive check` 与人审。

## 素材包结构

```json
{
  "version": 1,
  "deck": "Android面试",
  "instructions": "…",
  "candidates_format": {"items": [{"source_key": "…", "distractors": ["…"]}]},
  "count": 50,
  "cards": [
    {"source_key": "e452cdb31108", "section": "网络", "kind": "fact",
     "q": "…", "answer": "…", "source": "P12"}
  ]
}
```

## 候选格式

```json
{"items": [
  {"source_key": "e452cdb31108", "distractors": ["把图片按固定 30 帧每秒逐帧解码后缓存"]}
]}
```

- 每题最多 2 条；选项总数上限 5，已有 4 项时只剩 1 个位置（可用 `merge --replace-same-deck`）。
- 每条 2–60 字，不得与正确项、已有选项重复或高度相似。
- 长度尽量贴近 `correct_chars`（相差 ≤50%）；`check` 会对选项长度比 >2 的卡出提示。
- 只写干扰项，不要写正确项；正确项永远是源答案里的逐字片段。

## 给模型的提示词模板

> 你会收到一批面试题问答。只做一件事：为每道题写 1–2 个**看起来像正确答案、实际上是错的**
> 干扰项。要求：中文、2–60 字、与正确答案在主题上相邻但结论不同；不要复述正确答案；
> 不要编造原文没有的数字；不要解释。按 `{"items":[{"source_key":"…","distractors":["…"]}]}`
> 返回，只处理给定的 source_key。

## 人审清单

- `derive merge` 打印的「未并入」原因是否符合预期（重复、超长、选项已满）。
- 先用 `derive check --allow-model` 看两类提示：`review` 与「长度比」。
- 「需人工复审」逐条对照：干扰项是否明显荒谬、是否与正确答案同义。
- `derive report` 抽读 10 张含模型候选的题；答错的题是「干扰项太弱」还是「干扰项也说得通」。
- 选项满了又想要更多模型候选时，`merge --replace-same-deck` 只换同牌组项，换完仍需人审。
- 想要全模型干扰项：`plan --options 3` + `merge --prefer-model`，得到 1 正确 + 2 模型；
  代价是干扰项只剩 2 个，难度略降。
- 通过后再 `derive compile --allow-model-distractors`，源牌组不受影响。
