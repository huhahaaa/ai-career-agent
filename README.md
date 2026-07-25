# AI Career Agent

AI Career Agent 是一个面向课程综合项目的求职辅助平台，目标是完成岗位数据采集与审核、简历审核、岗位匹配、AI 模拟面试和报告生成的一体化流程。

## 当前进度

项目已从“框架搭建”推进到“数据、前端、向量检索联调”阶段。当前主线 `main` 可以作为阶段展示版本继续往后开发。

已完成内容：

- 后端基础：Python 3.11 + FastAPI + SQLAlchemy + SQLite。
- 用户认证：注册、登录、JWT Bearer Token、当前用户查询。
- 权限控制：普通学生账号与审核员账号，支持审核员专用接口。
- 数据材料：岗位原始数据、清洗后数据、审核记录、角色画像、技能词典。
- 岗位审核：岗位导入、列表查询、审核状态流转、已审核岗位查询。
- 向量检索：Chroma + SentenceTransformer，审核通过岗位可进入向量索引。
- 岗位匹配：根据简历或求职意向返回岗位、匹配分数、推荐理由和数据来源。
- 模拟面试：支持开始面试、提交回答并获得基础反馈。
- 前端联调：React/Vite 页面已接入认证、岗位、匹配、简历和面试相关入口。
- 测试验证：后端 pytest 通过，前端生产构建通过。

待完成内容：

- 简历文件上传、解析、版本管理和持久化。
- 面试历史、评分报告和训练建议持久化。
- 更完整的面试题库、STAR 评分规则和能力维度分析。
- 管理端统计看板、岗位收藏、投递跟踪等扩展功能。
- 最终报告、PPT、演示视频和三天项目日报整理。

## 核心流程

```text
岗位采集/导入 -> 清洗与技能提取 -> 岗位审核 -> 向量化入库 -> 简历审核 -> 岗位匹配 -> 模拟面试 -> 评分报告
```

## 技术框架

- 后端：Python 3.11 + FastAPI
- 数据库：SQLite，课程阶段优先保证轻量可运行，后续可切换 MySQL/PostgreSQL
- ORM：SQLAlchemy
- 认证：bcrypt + JWT Bearer Token
- 向量检索：Chroma + SentenceTransformer
- 前端：Vite + React
- 数据文件：JSONL、CSV、Markdown

## 目录结构

```text
ai-career-agent/
├─ backend/              # FastAPI 后端、数据库模型、接口、服务和测试
├─ frontend/             # React 前端页面、路由、API 客户端和样式
├─ data/                 # 岗位原始数据、清洗数据、审核样例和技能词典
├─ docs/                 # 分工、接口、流程、日报和贡献记录
├─ scripts/              # 数据初始化和辅助脚本
├─ .env.example          # 环境变量样例
└─ README.md
```

## 本地启动

后端：

```powershell
cd D:\PythonProject\ai-career-agent\backend
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip install -r requirements-vector.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

如需创建审核员账号：

```powershell
cd D:\PythonProject\ai-career-agent\backend
.\.venv\Scripts\python.exe -m app.commands.create_reviewer --username reviewer --email reviewer@example.com
```

导入已审核岗位到向量库：

```powershell
cd D:\PythonProject\ai-career-agent\backend
.\.venv\Scripts\python.exe scripts\index_jobs.py ..\data\processed\jobs_clean.jsonl
```

前端：

```powershell
cd D:\PythonProject\ai-career-agent\frontend
npm install
npm run dev
```

访问地址：

- 后端健康检查：http://127.0.0.1:8000/health
- 后端接口文档：http://127.0.0.1:8000/docs
- 前端页面：http://127.0.0.1:5173

## 分支与提交规范

`main` 只放通过阶段自测、可以展示的版本。每名成员使用自己的开发分支完成工作，再通过普通 merge 合并到 `main`。

推荐五人分支：

| 角色 | 分支名 | 主要负责 |
| --- | --- | --- |
| 组长/后端集成 | `hechang/project-scaffold`、`hechang/<feature>` | 项目骨架、后端基础、数据库、联调、阶段发布 |
| 数据审核 | `feature/job-data-audit` | 岗位采集、清洗、去重、审核记录、数据质量说明 |
| 向量匹配 | `feature/vector-matching` | Embedding、向量库、岗位检索、匹配理由 |
| 简历面试 | `feature/resume-interview-agent` | 简历审核、面试流程、评分反馈、报告草稿 |
| 前端测试 | `feature/frontend-testing` | 页面交互、接口联调、异常提示、测试记录、演示材料 |

提交要求：

- 每名成员至少保留 5 条有效 Git 提交记录。
- 提交信息建议写清楚模块和动作，例如 `feat(auth): add login api`、`docs(data): add audit workflow`。
- 合并成员分支时使用普通 merge，不使用 squash merge，避免个人提交被压缩成一条。
- 每次阶段合并后保留成员分支，便于老师按分支和提交记录检查。
- 统一贡献记录见 [docs/team-contribution-record.md](docs/team-contribution-record.md)。

## 常用验证

后端测试：

```powershell
cd D:\PythonProject\ai-career-agent\backend
.\.venv\Scripts\python.exe -m pytest
```

前端构建：

```powershell
cd D:\PythonProject\ai-career-agent\frontend
npm run build
```

查看成员提交：

```powershell
git log --oneline --all --graph
git shortlog -sn --all
```
