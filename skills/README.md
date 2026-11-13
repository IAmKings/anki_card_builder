# Skills

本目录存放可复制到其他 agent 的 skill。当前只有一个：`anki-card-builder`。

## 安装 `anki-card-builder`

两种方式，任选其一。

**A. 用 `npx skills add`**（需要 Node.js ≥ 22.20）：

```bash
# 默认装到当前项目的 .agents/skills/；加 -g 装到用户目录，跨项目可用
npx skills add IAmKings/anki_card_builder --skill anki-card-builder -a claude-code -y
```

`-a` 指定客户端（如 `claude-code`、`codex`、`cursor`），完整取值见 `npx skills --help`；不带参数运行会交互式选择 skill 与客户端。用这种方式装的副本用 `npx skills update` 升级。

**B. 手动复制**（不需要 Node）：

- 复制整个 `skills/anki-card-builder/` 目录到目标 agent 的 skills 目录（例如 `~/.agents/skills/`，具体以客户端文档为准）。
- 保持目录名为 `anki-card-builder`：`SKILL.md` 里的 `name` 必须与目录同名。

### 准备仓库与依赖

两种方式都只装说明文件，不含 `ankicards` 代码，所以先准备仓库与依赖：

```bash
git clone <this-repo>
cd anki_card_builder
python3 -m pip install -r requirements.txt

# 处理 PDF（ingest / 页面截图 / 裁图）时还需要：
python3 -m pip install -r requirements-render.txt
```

- 所有命令从仓库根目录运行。agent 的工作目录不在仓库根时，先 `cd` 过去，或把仓库根加入 `PYTHONPATH`。
- 验证安装：

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

用 `npx skills add` 装的副本：

```bash
npx skills update anki-card-builder
```

手动复制的副本先 `git pull`，然后用仓库里最新的 `skills/anki-card-builder/` 覆盖目标 agent 的旧副本。skill 的行为与仓库 CLI 绑定；升级仓库后不要保留旧 skill 副本。
