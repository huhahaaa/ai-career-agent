# 成员 2：8 次 Git 提交计划

目标分支：`黄林`

注意：本计划只提交到 `黄林`，不向 `main` 提交或合并。每次提交只包含一个明确的数据模块或文档模块，避免把所有文件集中到最后一次提交。

| 次数 | Commit message | 主要内容 | 验证方式 |
|---:|---|---|---|
| 1 | `data(source): add job collection scope and source registry` | 采集范围、来源登记、`.gitignore` 中允许提交审核数据 | `Import-Csv` 检查 24 条来源记录 |
| 2 | `data(raw): add publicly sourced job snapshots` | 公开岗位原始快照和来源证据摘要 | JSONL 逐行解析，检查 24 条 |
| 3 | `feat(clean): add normalized and reviewed job dataset` | 字段清洗、技能提取、岗位分类和统一审核字段 | JSONL 解析、类别统计、状态统计 |
| 4 | `feat(skill): add role profiles and skill normalization dictionary` | 六类岗位画像和技能同义词归一化 | JSON 解析，检查 6 个岗位画像 |
| 5 | `feat(review): add auditable job review records` | 审核人、审核时间、审核意见和审核状态 | 审核记录与岗位 ID 交叉检查 |
| 6 | `test(data): add job quality and audit edge cases` | 字段缺失、重复、乱码、技能归一化和索引过滤测试 | JSON 解析，检查 10 个案例 |
| 7 | `docs(data): add job data quality report` | 数量统计、类别分布、质量风险和下游交付说明 | 对照数据文件人工复核 |
| 8 | `docs(git): add member 2 eight-commit plan` | 本提交计划和分支提交约束 | `git log` 检查提交顺序和分支 |

## 推送命令

```powershell
git status -sb
git log --oneline -8
git push origin HEAD:黄林
```

推送前必须确认：

- 当前分支为 `黄林`；
- 工作区干净；
- 最近 8 次提交均属于成员 2 数据任务；
- 推送目标明确显示为 `origin/黄林`；
- 不执行 `git push origin main`，不创建主分支提交。

