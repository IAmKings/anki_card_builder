# GitHub Actions 自动打包发布 Anki 卡片

## Goal

push master 时自动将仓库中的 .apkg 文件上传到 GitHub Latest Release。

## Requirements

* push master 触发 workflow
* 直接上传 `output/Android面试卡组.apkg`（CI 不做构建，省 API 费用）
* 更新/创建 Latest Release
* .apkg 从 .gitignore 移除，纳入版本控制

## 工作流

```
本地手动生成卡片（有 API Key → 高质量）
  → git commit .apkg + push
    → CI 自动上传到 Latest Release
```

## Acceptance Criteria

* [ ] push master 时 workflow 触发
* [ ] .apkg 自动出现在 Latest Release 中
* [ ] 用户在 Release 页面可直接下载

## Technical Notes

* softprops/action-gh-release@v2 做上传
* 需要 contents: write 权限
* .apkg ~900KB，提交到 git 没问题
