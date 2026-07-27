# API 概览

基础地址：

```text
http://localhost:8000/api/v1
```

除 `/health` 外，API 使用统一响应结构：

```json
{
  "code": 0,
  "message": "success",
  "data": {}
}
```

错误响应保留 HTTP 状态码，同时提供业务错误码：

```json
{
  "code": 40102,
  "message": "authentication required",
  "data": null
}
```

## 认证

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `POST` | `/auth/register` | 注册 |
| `POST` | `/auth/login` | 登录 |
| `POST` | `/auth/logout` | 退出 |
| `GET` | `/auth/me` | 当前用户 |

公开注册固定创建 `student` 用户。审核员账号在 `backend` 目录执行以下命令创建：

```bash
python -m app.commands.create_reviewer --username reviewer --email reviewer@example.com
```

登录后在需要认证的请求中携带：

```text
Authorization: Bearer <access_token>
```

## 岗位数据

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `POST` | `/jobs/import` | 导入岗位，需登录 |
| `GET` | `/jobs` | 岗位列表，需登录 |
| `PATCH` | `/jobs/{job_id}/audit` | 审核岗位，仅 `reviewer` |
| `GET` | `/jobs/approved` | 已审核通过岗位，需登录 |

岗位导入、列表、审核和已通过查询已接入 SQLAlchemy 持久化。岗位信息保存到
`job_postings` 表，审核操作会写入 `job_review_records` 表。

## 简历与匹配

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `GET` | `/resumes` | 当前用户简历版本列表，需登录 |
| `POST` | `/resumes/upload` | 上传简历文件，需登录 |
| `GET` | `/resumes/{resume_id}` | 简历详情和版本内容，需登录 |
| `DELETE` | `/resumes/{resume_id}` | 删除简历，需登录 |
| `POST` | `/resumes/audit` | 简历审核，需登录 |
| `POST` | `/matching/run` | 岗位匹配，需登录 |
| `GET` | `/matching/history` | 当前用户岗位匹配历史，需登录 |
| `GET` | `/matching/skill-taxonomy` | 技能词表，需登录 |

简历上传目前完成文件保存、简历主表和版本表落库。PDF/DOC/DOCX 深度解析
仍属于后续简历解析模块；TXT/MD 可直接保存文本内容。用户直接粘贴简历
参与匹配或面试时，后端会自动保存一份简历快照，便于历史追踪。

`/resumes/audit` 会保存审核报告到 `resume_audit_reports` 表。请求中可选传入
`resume_id`，用于把审核报告关联到已上传简历版本。简历审核会进行空泛表达、
夸大风险、量化结果和岗位关键词检查，并通过 Agent 日志记录本次审核调用。

`/matching/run` 会保存可关联到数据库岗位的匹配结果。用户直接粘贴简历时，
后端会自动保存一份简历快照和版本记录，便于后续查看匹配历史。

## 面试 Agent

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `POST` | `/interviews/start` | 开始模拟面试，需登录 |
| `POST` | `/interviews/{session_id}/answer` | 提交回答并获得反馈，需登录 |
| `POST` | `/interviews/{session_id}/finish` | 结束面试并生成 STAR 报告和练习计划，需登录 |
| `GET` | `/interviews/history` | 当前用户面试记录，需登录 |
| `GET` | `/interviews/{session_id}/report` | 面试报告详情，需登录 |

当前面试接口会保存简历快照、面试会话、Agent 状态、用户回答、评分、反馈、
追问和下一轮问题。`/finish` 会生成综合得分、分项平均分、STAR 改写建议、
下一轮练习计划和总结，并保存到面试报告中。

面试 Agent 当前包含以下工作流节点：

1. 简历解析：提取技能、项目和经验关键词；
2. 岗位要求分析：结合目标岗位生成面试关注点；
3. 面试出题：生成不少于 8 个问题；
4. 追问判断：对过短、不具体、缺少技术关键词或量化结果的回答进行追问；
5. 结构化评分：按内容相关性、专业准确性、表达清晰度、STAR 完整性和岗位匹配度评分；
6. STAR 反馈：生成表达优化建议和练习计划。

面试启动、回答评分和报告生成会写入 `agent_logs` 表。

## 数据看板与 Agent 日志

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `GET` | `/admin/dashboard` | 当前用户数据看板，需登录 |
| `GET` | `/admin/metrics` | 审核员统计指标，仅 `reviewer` |

`/admin/dashboard` 返回前端看板所需的真实数据：

- 简历数量；
- 岗位数量；
- 面试次数；
- 平均分；
- 最近面试记录；
- 个人技能分布；
- 热门岗位技能需求；
- 个人能力与岗位要求雷达图数据；
- 多岗位匹配得分；
- 面试得分趋势；
- 岗位城市分布；
- 当前用户 Agent 调用次数。

`agent_logs` 表用于保存智能体调用记录，字段包括操作名称、状态、耗时、请求摘要、
响应摘要、错误信息和创建时间。目前已记录：

- `interview.start`
- `interview.answer`
- `interview.finish`
- `resume.audit`

## 权限错误码

| 错误码 | 说明 |
| ---: | --- |
| `40101` | 用户名或密码错误 |
| `40102` | 缺少 Token，或 Token 无效、过期 |
| `40103` | 用户已停用或不存在 |
| `40301` | 当前角色权限不足 |
| `40901` | 用户名已存在 |
| `40902` | 邮箱已存在 |
| `42200` | 请求参数校验失败 |
