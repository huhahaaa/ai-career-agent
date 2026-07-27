# Day 2 数据材料与审核说明

更新时间：2026-07-26（Asia/Shanghai）  
负责人：第一组｜黄林（成员2，数据审核）

## 1. 材料清单

| 材料 | 文件 | 数量 | 用途 |
| --- | --- | ---: | --- |
| 脱敏简历 | `data/audit_samples/resume_samples.jsonl` | 10 | 测试简历解析、简历质量分层和岗位匹配 |
| 岗位 JD | `data/audit_samples/job_jd_samples.jsonl` | 10 | 测试岗位展示、技能匹配和来源校验 |
| 岗位画像 | `data/processed/role_profiles.json` | 6 | 统一岗位别名、必备技能、加分技能和证据信号 |
| 面试题库 | `data/audit_samples/interview_questions.jsonl` | 30 | 测试按岗位生成问题、评分要点和追问 |
| 失败案例 | `data/audit_samples/day2_failure_cases.json` | 6 | 测试边界输入、错误提示和降级策略 |

## 2. 数据来源与更新时间

- 岗位基础数据来自前一天整理的公开 Greenhouse/Ashby 官方 ATS 页面，完整来源登记在 `data/raw_jobs/job_sources.csv`，清洗后的记录在 `data/processed/jobs_clean.jsonl`。
- 岗位 JD 测试集从已审核岗位中抽取并统一字段；`source_link` 是追溯入口，`source_checked_at` 是本轮最后核验时间，`source_update_note` 记录页面是否给出发布日期或开始时间。
- 简历、面试题和失败案例是人工设计的合成测试数据，不代表真实候选人或真实投递材料；简历中的姓名、联系方式、学校和组织均使用泛化描述。
- 岗位页面可访问只表示来源可追溯，不表示岗位当前仍接受投递；演示前应再次复核页面状态。

## 3. 主要字段说明

### 简历

`resume_id` 是稳定测试编号；`target_role` 用于期望岗位标签；`skills` 是规范化技能数组；`projects` 和 `experience` 保存职责及结果证据；`quality_level` 用于强/弱样本测试；`sensitive_data_removed` 必须为 `true`。

### 岗位

`jd_id` 是测试编号，`source_id` 对应原始岗位记录；`source_site`、`source_link`、`source_checked_at` 共同构成可追溯来源；`title`、`company`、`location` 是展示必填字段；`skills` 和 `requirements` 用于匹配与解释。

### 面试题

`question_id` 是稳定编号；`role` 关联岗位画像；`category` 区分技术基础、项目深挖和场景题；`expected_points` 是评分证据；`follow_up` 是信息不足时的追问；`scoring_tags` 用于筛选和统计。

## 4. 清洗规则

1. 统一岗位类别、岗位别名和技能名称，去除同义重复项。
2. 岗位正文只保留岗位职责、任职要求和公开岗位元数据，不保存联系人、招聘邮箱或个人信息。
3. 缺失的发布日期、地点或薪资不猜测，使用“未标注”并在 `source_update_note` 或审核意见中说明。
4. 简历样本保留能证明能力的项目、行动和结果；删除手机号、邮箱、身份证号、详细住址等敏感字段。
5. JSONL 每行必须是独立合法 JSON；数组字段不得使用逗号拼接的自由文本代替。

## 5. 审核规则

- 岗位进入 `approved` 前必须具备标题、公司、岗位正文、来源链接，并至少提取 3 个技能或能力标签。
- 简历样本必须可解析，至少包含教育背景、技能、项目或经历中的两类证据；弱样本可以缺少部分字段，但要明确 `quality_level`。
- 面试题必须能映射到一个岗位画像，并同时提供评分要点和追问，避免只有“谈谈你的看法”而没有可审核标准。
- 发现简历过短、来源缺失、无匹配结果、回答过短或岗位过期时，按 `day2_failure_cases.json` 的预期行为降级处理，不伪造结果。
- 数据审核记录由成员2维护；演示前由项目负责人复核来源页面状态和更新时间。

## 6. 验收口径

本批材料应满足：10 份简历、10 条岗位 JD、至少 5 类岗位画像、30 道面试题、至少 4 类失败案例；岗位来源字段齐全；数据文件可以被 JSON/JSONL 解析；文档可以追溯来源、更新时间、字段、清洗和审核规则。
