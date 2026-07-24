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

当前岗位接口仍使用内存存储，供数据采集成员在其分支替换为 SQLAlchemy 持久化实现。

## 简历与匹配

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `POST` | `/resumes/audit` | 简历审核，需登录 |
| `POST` | `/matching/run` | 岗位匹配，需登录 |
| `GET` | `/matching/skill-taxonomy` | 技能词表，需登录 |

## 面试 Agent

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `POST` | `/interviews/start` | 开始模拟面试，需登录 |
| `POST` | `/interviews/{session_id}/answer` | 提交回答并获得反馈，需登录 |

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
