# 团队贡献记录

本文件用于统一记录五名成员的分支、模块、提交数量和代表性工作，避免只给某一名成员单独写贡献说明。

## 填写规则

- 每名成员至少保留 5 条有效 Git 提交记录。
- 代表提交优先选择能说明具体功能、数据、测试或文档工作的提交。
- 合并到 `main` 时使用普通 merge，不使用 squash merge。
- 阶段合并后保留成员分支，便于课程检查。
- 个人日报、测试截图和功能说明可以放在 `docs/` 下，但命名和结构应保持一致。

## 成员记录表

| 成员 | GitHub 身份 | 分支 | 负责模块 | 当前状态 | 提交数 | 代表提交 |
| --- | --- | --- | --- | --- | ---: | --- |
| 组长/后端集成 | 待填写 | `hechang/project-scaffold`、`hechang/<feature>` | 项目骨架、认证权限、数据库、接口联调、阶段合并 | 进行中 | 待统计 | 待填写 |
| 数据审核 | 待填写 | `feature/job-data-audit` | 岗位采集、清洗、去重、审核记录、数据质量报告 | 进行中 | 待统计 | 待填写 |
| 向量匹配 | 待填写 | `feature/vector-matching` | Embedding、向量库、岗位检索、匹配理由 | 进行中 | 待统计 | 待填写 |
| 简历面试 | 待填写 | `feature/resume-interview-agent` | 简历审核、模拟面试、评分反馈、报告草稿 | 待推进 | 待统计 | 待填写 |
| 前端测试 | 待填写 | `feature/frontend-testing` | 页面交互、接口联调、异常提示、测试记录、演示材料 | 进行中 | 待统计 | 待填写 |

## 统计命令

查看所有分支提交：

```powershell
git log --oneline --all --graph
```

按作者统计提交数量：

```powershell
git shortlog -sn --all
```

查看某个分支相对 `main` 的新增提交：

```powershell
git log --oneline main..分支名
```

查看某个作者的提交：

```powershell
git log --oneline --all --author="作者名或邮箱"
```
