# 团队分支与提交规范

## 结论

组长也建议使用自己的开发分支，不建议长期直接在 `main` 分支提交业务代码。

`main` 的定位是稳定主线，用来放已经通过自测、可以展示的版本。个人开发、联调修复、文档补充都应该先在个人分支完成，再合并到 `main`。

## 推荐分支

| 角色 | 分支名 | 主要负责 |
| --- | --- | --- |
| 组长 | `leader/project-scaffold` | 项目骨架、后端基础、数据库、集成、发布 |
| 成员 A | `feature/job-data-audit` | 岗位采集、清洗、去重、审核 |
| 成员 B | `feature/vector-matching` | 知识库、Embedding、向量检索、岗位匹配 |
| 成员 C | `feature/resume-interview-agent` | 简历审核、面试 Agent、评分报告 |
| 成员 D | `feature/frontend-testing` | 前端页面、可视化、测试记录、演示材料 |

## 提交要求

每个人至少 5 条有效提交，建议 7 到 9 条。有效提交应该能看出具体工作内容，例如：

```text
feat(jobs): add job import endpoint
feat(jobs): implement pending approved rejected audit flow
feat(resume): add vague phrase risk detection
feat(interview): scaffold interview agent tools
test(api): add health and job audit tests
docs(report): add data audit workflow section
```

## 合并规则

- 不要直接在 `main` 上做日常开发。
- 每个成员从 `main` 拉自己的分支。
- 每完成一个小功能就提交一次，不要把一整天内容压成一条。
- 合并时不要 squash merge，否则个人提交记录会被压缩。
- 每次阶段性合并后打标签，例如 `v0.1.0-scaffold`、`v0.2.0-data-audit`、`v1.0.0-final`。

