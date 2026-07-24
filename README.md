# AI Career Agent

AI Career Agent 是一个面向课程综合项目的求职辅助平台，覆盖岗位数据采集与审核、简历审核、岗位匹配、AI 模拟面试和报告生成。

## 核心流程

```text
岗位采集/导入 -> 清洗与技能提取 -> 岗位审核 -> 向量化入库 -> 简历审核 -> 岗位匹配 -> 模拟面试 -> 评分报告
```

## 技术框架

- 后端：FastAPI
- 前端：Vite + React
- 数据库：SQLite 起步，后续可切换 MySQL/PostgreSQL
- 知识库/向量检索：先预留 `services/vector_store.py`，后续接 Chroma、FAISS 或 Milvus
- Agent：先预留面试 Agent 服务层，后续补充 3 个以上工具节点

## 目录结构

```text
ai-career-agent/
├─ backend/              # FastAPI 后端
├─ frontend/             # React 前端
├─ data/                 # 岗位原始数据、处理数据、审核样例
├─ docs/                 # 分工、接口、流程、日报模板
├─ scripts/              # 数据初始化和辅助脚本
├─ .env.example          # 环境变量样例
└─ README.md
```

## 本地启动

后端：

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

前端：

```bash
cd frontend
npm install
npm run dev
```

访问地址：

- 后端健康检查：http://localhost:8000/health
- 后端接口文档：http://localhost:8000/docs
- 前端页面：http://localhost:5173

## 分支规则

`main` 只放稳定版本，不建议任何人长期直接在 `main` 开发。组长也应该使用自己的分支，例如：

```text
hechang/project-scaffold
```

推荐五人分支：

```text
hechang/project-scaffold
feature/job-data-audit
feature/vector-matching
feature/resume-interview-agent
feature/frontend-testing
```

每个人至少保留 5 条有效提交，建议目标是 7 到 9 条。合并时不要使用 squash merge，否则个人提交记录会被压成一条。

## 当前阶段

当前仓库处于第一阶段：项目框架搭建。重点是让每个成员可以从清晰边界开始开发，不在同一批文件里互相冲突。
