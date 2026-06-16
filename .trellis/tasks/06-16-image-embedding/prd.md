# MD 图片嵌入 Anki 卡片

> **状态**: 暂缓实施，等待反馈

## Goal

支持 MD 文件中的 `![](path)` 本地图片嵌入到 Anki 卡片中。

## Background

当前 MD 文件中的图片引用 `![](path)` 被清洗掉，无法进入卡片。Anki 原生支持
media 文件嵌入（.apkg 本质是 zip），genanki 有 `Package.media_files` API。

## Technical Approach

### 需要改动的模块

| 模块 | 改动 |
|------|------|
| `src/parsers/kotlin_md.py` | `_clean_answer()` 中检测 `![](path)` → `<img src="hash.png">` |
| `src/utils.py` | 新增 `collect_media_files()` 扫描所有被引用的图片 |
| `src/pipeline.py` | 流水线中调用 media 收集 |
| `src/export/anki_exporter.py` | `export()` 接受 `media_files` 参数传给 genanki |
| `src/export/anki_exporter.py` | CSS 新增 `img { max-width: 100%; }` |

### 处理流程

```
MD 解析 → 检测 ![](path) → 复制图片到 output/media/
       → 重命名为 hash 避免冲突
       → 替换为 <img src="hash.png">
       → genanki.Package(deck, media_files=[...])
```

### 文件命名策略

```
data/diagrams/thread-model.png  →  output/media/a3f8c2d1.png (sha256前8位)
```

避免不同 MD 文件引用同名图片的冲突。

## Open Questions

- [ ] 是否需要支持远程 URL 图片？(Anki 不支持，需先下载)
- [ ] 图片大小限制？(建议 >100KB 自动压缩/jpg 转换)
- [ ] SVG 支持？(Anki WebView 通常支持)

## Risks

| 风险 | 影响 | 缓解 |
|------|------|------|
| .apkg 体积暴增 | 100张截图 = 20MB+ | 自动压缩 + 大小警告 |
| 图片路径不存在 | 构建失败 | 跳过 + 日志告警 |
| 远程图片失效 | 卡片内容缺失 | 下载到本地缓存 |

## Acceptance Criteria

* [ ] `![](data/diagrams/x.png)` 正确嵌入卡片
* [ ] 同名图片自动 hash 重命名
* [ ] .apkg 中 media 文件可被 Anki 识别
* [ ] 图片不存在时有明确日志提示，不阻断构建

## Out of Scope

* 远程 URL 图片自动下载（第一版不做）
* SVG 特殊处理
* 图片 OCR / 文字提取
