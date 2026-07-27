# Day2 补充报告：AI 求职辅导系统「真正跑通」（含向量语义匹配）

> 目标：在本地把组长的真实版本完整跑起来，并打通此前一直 503 的**向量语义岗位匹配**功能。
> 时间：2026-07-26
> 环境：Windows / Python 3.11.9（venv）/ FastAPI / chromadb 0.5.23 / sentence-transformers 3.3.1

## 一、本次新增做了什么

此前基础功能已通（岗位、看板、简历审计、面试、历史），但 `POST /api/v1/matching/run` 因缺少向量服务一直返回 503。本次补齐向量链路：

1. **重建 Python 3.11.9 虚拟环境**（`backend/venv`），安装核心依赖 `requirements.txt`。
2. **安装向量依赖** `requirements-vector.txt`（chromadb + sentence-transformers）。
3. **配置运行参数** `.env`：`LLM_PROVIDER=mock`（无需任何外部 API Key 即可跑通全流程）。
4. **灌入并索引岗位**：运行 `python scripts/sync_clean_jobs.py --rebuild-index`，
   将数据库中 24 条 `approved` 岗位写入 chroma 向量库（首次自动下载多语言嵌入模型
   `paraphrase-multilingual-MiniLM-L12-v2`，约 400MB）。索引结果：`indexed_count=24`。
5. **重启后端** `uvicorn app.main:app --host 127.0.0.1 --port 8000`（用带向量依赖的 venv 启动）。

## 二、实测结果（端到端）

| 项目 | 结果 |
| --- | --- |
| `/health` | 200 `{"status":"ok","service":"AI Career Agent"}` |
| 岗位库 | 24 条 approved（6 大类） |
| 向量索引 | 24 条岗位已写入 chroma |
| `POST /api/v1/matching/run` | **200**（此前 503，现已消除） |
| 匹配返回 | 5 条，含 `semantic_score` / `skill_coverage_score` / `matched_skills` |

示例匹配（简历含 Python/FastAPI/SQL/LLM/RAG，目标岗位「后端」）：

```
Software Engineer Intern - Summer 2026   score=74.77  semantic=74.0   matched=[Python, React, LLM]
Software Engineer Intern - Backend       score=68.16  semantic=72.86  matched=[Python]
Software Engineer Intern                score=67.23  semantic=75.39  matched=[Python]
Software Engineer Intern (Backend,Rust) score=57.91  semantic=71.75  matched=[]
Product Manager Intern - Checkout       score=43.06  semantic=71.76  matched=[]
```

语义分与技能覆盖率分均正常产出，说明 chromadb 检索 + 句向量召回已真正生效。

## 三、怎么用（给组长的接入说明）

- **API 文档（Swagger）**：浏览器打开 `http://127.0.0.1:8000/docs`
  （本次已用 Edge 打开）。
- **鉴权**：`POST /api/v1/auth/register` 注册（角色默认 student）→
  `POST /api/v1/auth/login` 拿 `access_token` → 在其它接口 Header 带
  `Authorization: Bearer <token>`。
- **测匹配**：`POST /api/v1/matching/run`，body：
  ```json
  { "resume_text": "简历文本…", "target_position": "后端", "top_k": 5 }
  ```
- **前端（可选）**：项目根目录 `npm install && npm run dev` → `http://localhost:5173`。

## 四、踩坑与注意点

1. **Python 版本**：系统 3.13 无法编译 pydantic 2.7.4，必须用 3.11.x。
2. **端口占用**：若 8000 被旧进程占用，先 `Stop-Process` 再重启，否则 uvicorn 启动报
   `Errno 10048`。
3. **索引前置条件**：只有 `status='approved'` 的岗位才会进向量库；
   索引接口 `/matching/index/approved` 需 `reviewer` 角色，普通账号用
   `sync_clean_jobs.py --rebuild-index` 脚本绕过即可。
4. **模型下载**：首次索引需联网下载约 400MB 嵌入模型（Windows 无符号链接会有告警，
   不影响使用）。

## 五、结论

组长真实版本已在本地**完整可运行**，包括此前未通的向量语义匹配。基础功能 + 向量匹配
全链路打通，可交付后续测试。
