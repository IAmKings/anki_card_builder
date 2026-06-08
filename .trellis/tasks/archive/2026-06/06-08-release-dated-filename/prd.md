# Release 文件名带日期

## Goal

Release 的 tag_name 和 asset 文件名包含日期（如 `2026-06-08`），而非固定 `latest`。

## Requirements

* tag_name 使用日期格式：`release-YYYY-MM-DD`
* 每次 push 创建独立 Release（非覆盖 latest）
