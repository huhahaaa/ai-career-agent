# Day 2 Data Audit Materials Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 补齐题目 7 第二天验收所需的脱敏简历、岗位 JD、岗位画像、面试题和失败案例，并记录可追溯的数据规则。

**Architecture:** 复用现有 `data/processed/jobs_clean.jsonl` 与 `role_profiles.json` 的字段约定，在 `data/audit_samples/` 增加面向测试的 JSONL/JSON 数据。所有样本使用虚构或已脱敏内容；文档统一说明来源、更新时间、清洗和审核规则。

**Tech Stack:** JSONL、JSON、Markdown、PowerShell JSON 解析、Git。

## Global Constraints

- 不采集或提交真实个人联系方式、身份证号、地址等隐私信息。
- 每条岗位测试数据必须有来源、标题、公司、地点、技能和更新时间。
- 最终材料必须包含 10 份简历、10 条岗位 JD、至少 5 类岗位画像、30 道面试题和至少 4 类失败案例。
- 所有改动提交到 `黄林` 分支，不修改主分支。

---

### Task 1: Add de-identified resume samples

**Files:**
- Create: `data/audit_samples/resume_samples.jsonl`

- [ ] 写入 10 份虚构简历，覆盖前端、后端、产品、运营、算法/机器学习、数字媒体，并包含强样本和弱样本。
- [ ] 确保字段包含 `resume_id`、`target_role`、`education`、`skills`、`projects`、`experience`、`quality_level`、`sensitive_data_removed`。
- [ ] 使用 JSONL 解析校验并提交：`data(resume): add de-identified resume samples`。

### Task 2: Add job JD test samples

**Files:**
- Create: `data/audit_samples/job_jd_samples.jsonl`

- [ ] 写入 10 条可用于匹配和审核的 JD 测试样本。
- [ ] 每条包含 `jd_id`、`source_site`、`source_link`、`source_checked_at`、`title`、`company`、`location`、`skills`、`requirements`。
- [ ] 校验必填字段和数量并提交：`data(job): add job JD test samples`。

### Task 3: Enrich role profiles and add interview question bank

**Files:**
- Modify: `data/processed/role_profiles.json`
- Create: `data/audit_samples/interview_questions.jsonl`

- [ ] 给已有画像补充 `profile_version`、`updated_at`、`data_source` 和关联测试数据字段。
- [ ] 写入 30 道面试题，覆盖 6 类岗位、基础/项目/场景题，并提供评分要点与追问。
- [ ] 校验题目数量、岗位覆盖和字段完整性并提交：`data(interview): add categorized interview question bank`。

### Task 4: Record failure cases and audit documentation

**Files:**
- Create: `data/audit_samples/day2_failure_cases.json`
- Create: `docs/day2-data-audit.md`

- [ ] 记录简历过短、岗位无来源、匹配结果为空、回答过短触发追问 4 类失败案例及预期处理。
- [ ] 文档说明数据来源、更新时间、字段定义、清洗规则、审核规则、隐私处理和复核责任。
- [ ] 校验失败案例不少于 4 条、文档包含全部规则关键词，并提交：`docs(data): document day 2 source and audit rules`。

### Task 5: Verify and publish branch

- [ ] 运行 JSON/JSONL 数量和字段检查。
- [ ] 运行 `git diff --check`，确认没有未预期文件。
- [ ] 将最终改动推送到 `origin/黄林`。
- [ ] 使用 `git ls-remote --heads origin 黄林` 核验远端分支已更新。
