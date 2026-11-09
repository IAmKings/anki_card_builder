# Skills

本目录存放可复制到其他 agent 的 skill。当前只有一个：`anki-card-builder`。

## 安装 `anki-card-builder`

1. 复制整个 `skills/anki-card-builder/` 目录到目标 agent 的 skills 目录（例如 `~/.agents/skills/`，具体以客户端文档为准）。
2. 保持目录名为 `anki-card-builder`：`SKILL.md` 里的 `name` 必须与目录同名。
3. 这个 skill 不是独立可执行包，依赖本仓库的 `ankicards` 代码。先准备仓库与依赖：

   ```bash
   git clone <this-repo>
   cd anki_card_builder
   python3 -m pip install -r requirements.txt

   # 处理 PDF（ingest / 页面截图 / 裁图）时还需要：
   python3 -m pip install -r requirements-render.txt
   ```

4. 所有命令从仓库根目录运行。agent 的工作目录不在仓库根时，先 `cd` 过去，或把仓库根加入 `PYTHONPATH`。
5. 验证安装：

   ```bash
   python3 -m ankicards --help
   python3 -m unittest discover -s tests
   ```

## 依赖与运行环境

| 依赖 | 用途 | 是否必需 |
|---|---|---|
| Python 3.12 | 运行 CLI | 必需 |
| `requirements.txt` | `genanki`、`python-docx`、`lxml` 等 | 必需 |
| `requirements-render.txt` | PyMuPDF，PDF ingest/截图/裁图 | 处理 PDF 时必需 |
| 本仓库 checkout | `ankicards` 包与数据布局 | 必需 |
| `data/Android/`、`data/MQTT/` | 公开复现材料 | 可选 |

该 skill 没有其他 skill 依赖；它依赖仓库代码和上述 Python 包，不依赖网络服务或私有 API。

## 数据与安全

- 公开材料放 `data/Android/`、`data/MQTT/`。
- 非公开材料只放本地目录，并加入本机 `.git/info/exclude`；不要提交、不要发布。
- 含内页截图的 `.apkg`、预览 HTML 同样按非公开材料处理。

## 更新

```bash
git pull
```

然后用仓库里最新的 `skills/anki-card-builder/` 覆盖目标 agent 的旧副本。skill 的行为与仓库 CLI 绑定；升级仓库后不要保留旧 skill 副本。
