# API 概览

基础地址：

```text
http://localhost:8000/api/v1
```

## 认证

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `POST` | `/auth/register` | 注册 |
| `POST` | `/auth/login` | 登录 |
| `POST` | `/auth/logout` | 退出 |
| `GET` | `/auth/me` | 当前用户 |

## 岗位数据

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `POST` | `/jobs/import` | 导入岗位 |
| `GET` | `/jobs` | 岗位列表 |
| `PATCH` | `/jobs/{job_id}/audit` | 审核岗位 |
| `GET` | `/jobs/approved` | 已审核通过岗位 |

## 简历与匹配

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `POST` | `/resumes/audit` | 简历审核 |
| `POST` | `/matching/run` | 岗位匹配 |
| `GET` | `/matching/skill-taxonomy` | 技能词表 |

## 面试 Agent

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `POST` | `/interviews/start` | 开始模拟面试 |
| `POST` | `/interviews/{session_id}/answer` | 提交回答并获得反馈 |

