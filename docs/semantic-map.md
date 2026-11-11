# 语义地图：在单份文档/牌组内部找关联

`scripts/semantic_map.py` 读一份已编译的牌组目录，编码每张卡的 `q + a`，用余弦相似度给出：

- **邻居**：每张卡最相近的 5 张；
- **簇**：互惠 top-5 边上的 Louvain 社区，用作文档内的主题热点；
- **近重复**：相似度 ≥ 0.90 的卡对；
- **中心度**：加权 PageRank，找核心知识点；
- **孤立点**：不属于任何簇的卡。

它只写报告（`semantic.json` / `semantic.md`），**不写卡片、不改 plan、不进 CI**。

## 为什么不用 txtai / 向量库

单份文档只有几百到一两千张卡，512 维向量在内存里做全量余弦足够；引入服务、向量库或 Docker 属于过度工程。依赖压到四个包：`numpy`、`tokenizers`、`onnxruntime`、`networkx`。

## 安装

```bash
pip install -r requirements-rag.txt

# 模型（约 95MB）。二选一：
huggingface-cli download Xenova/bge-small-zh-v1.5 --include "onnx/model.onnx" --local-dir ~/models/bge-small-zh
# 或整仓克隆后指向 BAAI/bge-small-zh-v1.5（torch 版不适用本脚本）
```

模型目录里应有 `onnx/model.onnx`（或 `model.onnx`）和 `tokenizer.json`。

## 跑法

```bash
python3 scripts/semantic_map.py \
  --deck /tmp/derive_probe/android \
  --model ~/models/bge-small-zh \
  --out-dir .work/semantic \
  --threshold 0.60 --top-k 5 --dup-threshold 0.90
```

默认输出到 `.work/semantic/`（已在 `.gitignore`）。

| 参数 | 默认 | 说明 |
|---|---|---|
| `--threshold` | 0.60 | 建边的最小余弦；不同牌组需重扫 |
| `--top-k` | 5 | 每点最多连出的邻居数；边要双向互惠 |
| `--dup-threshold` | 0.90 | 近重复判定 |
| `--resolution` | 1.0 | Louvain 分辨率，越大簇越多 |
| `--limit` | 0 | 只取前 N 张卡（调试用） |
| `--centrality` | 20 | 报告里列出的中心卡数量 |
| `--json-only` | 关 | 只写 JSON |

## 输出

`semantic.json`：

```json
{
  "version": 1,
  "deck": {"name": "...", "cards": 1270, "sections": [...]},
  "model": {"name": "bge-small-zh-v1.5", "sha256": "...", "dim": 512},
  "params": {"threshold": 0.6, "top_k": 5, "dup_threshold": 0.9},
  "cards": [{"key": "...", "section": "...", "q": "...", "cluster": "c1"}],
  "clusters": [{"id": "c1", "size": 79, "label": "...", "sections": {...}, "members": ["..."]}],
  "neighbors": [{"key": "...", "top": [{"key": "...", "score": 0.91}]}],
  "duplicates": [{"a": "...", "b": "...", "score": 0.95, "q_a": "...", "q_b": "..."}],
  "centrality": [{"key": "...", "score": 0.004, "rank": 1}],
  "singletons": ["..."],
  "stats": {"clusters": 190, "edges": 1638, "duplicates": 29, "singletons": 126, "max_cluster": 79, "elapsed_s": 15.2}
}
```

`semantic.md` 是同一份数据的人读版本：总览、前 20 个簇（大小/标签/主要 section/示例题）、近重复、中心卡、孤立点。

## 确定性

同输入两次运行，`semantic.json` 逐字节相同（已实测）：Louvain 固定 `seed=7`、边按分数排序、报告内所有列表稳定排序、不写时间戳。

## M0 实测（Android 1270 张，bge-small-zh ONNX）

| 指标 | 结果 |
|---|---|
| 耗时 | 15–17 秒（CPU） |
| 簇 / 边 / 近重复 / 孤立 | 190 / 1638 / 29 / 126 |
| top-5 邻居相关 | 18/20 |
| 簇标签可读 | 6/8 |
| 近重复为真 | 12/12 |

**连通分量不能用**：τ=0.50–0.65 时几乎整组连成一个巨簇（1270/1270），链式效应；改用 Louvain。

## 局限与边界

- 簇不是章节：section 只是源文件划分，聚类结果会跨 section。
- 标签是词面统计（按虚词切块 + tf×idf），不是语义命名；只作提示。
- 阈值依赖牌组分布，换牌组要重扫，不要在脚本里写死。
- 只处理单份文档内的关系；不做跨文件、跨牌组。
- 中文短问答容易同质化（大量「是什么」），所以嵌入 `q + a` 而不是只嵌入 `q`。
- 模型与计算全本地；脚本不发起网络请求（首次下载由人手动执行）。
- 不在 CI 里跑：模型体积与耗时都不适合每次构建。M1 只产出报告；用关系生成种子/干扰项池是 M2。

## 与 derive 的关系（M2，未实现）

- 同簇邻居 → 出「区别/对比」类问题候选；
- 近重复 → 合并或改写建议；
- 中心度 → 优先补卡/换问法；
- `derive merge` 的 T1 干扰项池可以换成「语义近邻但答案不同」的卡，而不是随机同牌组池。

这些都要先有报告，人工抽查通过后再接。
