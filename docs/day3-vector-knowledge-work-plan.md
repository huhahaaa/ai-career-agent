# Day3 向量库与知识库优化分工建议

## 目标

核心任务是   把离线知识材料真正接入向量检索、岗位匹配解释和多岗对比流程，让用户能看见系统参考了哪些知识，以及为什么给出当前匹配结果。

建议主题：

> 把离线知识材料接入向量检索与匹配解释，让知识库真正影响用户结果。

## 当前项目知识库现状

项目目前已经有知识库材料，也有部分业务接入，但还不是完整的 RAG 知识库系统。

已有知识材料主要包括：

- `data/processed/role_profiles.json`：岗位能力画像
- `data/processed/skill_dictionary.json`：技能词典
- `data/processed/jobs_clean.jsonl`：原始清洗岗位数据
- `data/processed/jobs_chinese.jsonl`：中文岗位数据
- `data/audit_samples/interview_questions.jsonl`：面试题库
- `data/audit_samples/job_jd_samples.jsonl`：岗位 JD 样例
- `data/audit_samples/resume_samples.jsonl`：脱敏简历样例
- `data/audit_samples/test_cases.json`：数据测试样例
- `data/audit_samples/day2_failure_cases.json`：失败案例
- `data/raw_jobs/job_sources.csv`：岗位来源记录

当前已接入业务的部分：

- 简历审核会参考岗位能力画像，判断缺失关键词和岗位不匹配点。
- 岗位匹配会参考岗位画像，生成命中技能、缺失技能、能力缺口和修改建议。
- 面试 Agent 会把岗位能力画像加入 Prompt，让问题和反馈更贴近目标岗位。
- 后台已有知识库概览接口，用于查看当前知识材料数量和用途。

当前不足：

- 向量库主要索引已审核岗位 JD，还没有统一索引岗位画像、技能词典、面试题库等知识文件。
- 匹配结果还没有完整展示“引用了哪些知识来源”。
- 技能缺口没有稳定区分“核心技能”和“加分技能”。
- 多岗对比还没有输出共同能力缺口总结。
- 知识材料已经存在，但用户对这些材料的感知还不够明显。

## 今日建议任务

### 1. 新增知识文档加载器

目标：把散落在 `data/` 目录下的知识材料统一转成可检索文本。

建议新增文件：

```text
backend/app/services/rag_knowledge_loader.py
```

建议读取这些文件：

```text
data/processed/role_profiles.json
data/processed/skill_dictionary.json
data/audit_samples/interview_questions.jsonl
data/audit_samples/job_jd_samples.jsonl
```

统一转换为类似结构：

```python
{
    "doc_id": "role_backend",
    "doc_type": "role_profile",
    "title": "后端开发岗位能力画像",
    "content": "后端开发必备能力包括 Python/Java、SQL、接口开发、后端框架...",
    "metadata": {
        "role": "后端开发",
        "source": "role_profiles.json"
    }
}
```

这样岗位画像、技能词典、面试题库就不只是离线文件，而是可以被统一检索和引用的知识文档。

### 2. 扩展向量索引范围

目标：让向量库不只索引已审核岗位 JD，也能索引知识库文档。

可选实现方式：

```text
backend/scripts/index_knowledge.py
```

或者后台接口：

```text
POST /api/v1/admin/knowledge/index
```

建议进入知识库索引的材料：

- 岗位能力画像
- 技能词典
- 岗位 JD 样例
- 面试题库

暂不建议索引用户简历样例：

```text
data/audit_samples/resume_samples.jsonl
```

原因是简历样例更适合作为测试数据和演示基线，不应该混入正式匹配知识库，避免影响真实用户匹配结果。

向量索引 metadata 至少包含：

```python
doc_type
source_file
role
title
```

这样后续匹配结果可以展示引用来源。

### 3. 匹配结果增加知识引用

目标：用户看到匹配分数时，能知道系统参考了什么，而不是只看到一个分数。

建议在匹配结果中增加字段：

```json
"references": [
  {
    "type": "role_profile",
    "title": "后端开发岗位能力画像",
    "reason": "用于判断核心技能缺口",
    "source": "role_profiles.json"
  },
  {
    "type": "job_jd",
    "title": "Python后端开发实习生JD",
    "reason": "用于补充岗位技能要求",
    "source": "job_jd_samples.jsonl"
  }
]
```

前端后续可展示为：

```text
参考依据：
- 后端开发岗位能力画像
- 当前岗位 JD 技能要求
- 技能词典：Python / SQL / FastAPI
```

这能明显增强匹配结果可信度。

### 4. 技能缺口分层

目标：避免用户误解为“想高分就必须会一大堆技术”，让系统更贴近真实求职场景。

建议把技能缺口拆成：

```json
"skill_gap_detail": {
  "core_missing": ["后端框架", "SQL"],
  "bonus_missing": ["Docker", "Redis"],
  "matched_core": ["Python", "接口开发"],
  "matched_bonus": ["Git"]
}
```

前端可展示为：

```text
核心能力：Python、接口开发 已命中；SQL 待补充
加分能力：Redis、Docker 暂未体现
```

这样用户能区分：

- 哪些是必须补的核心能力
- 哪些是加分项
- 哪些只是泛化能力或附加能力

### 5. 多岗对比增加共同能力缺口

目标：多岗对比不只是展示薪资、城市、匹配度，还能告诉用户应该优先补什么。

建议新增服务函数：

```python
compare_job_skill_gaps(job_ids, resume_text)
```

建议输出：

```json
{
  "common_required_skills": ["Python", "SQL", "接口开发"],
  "common_missing_skills": ["Redis", "Docker"],
  "job_specific_gaps": [
    {
      "job_id": 1,
      "title": "Python后端开发实习生",
      "extra_missing": ["FastAPI"]
    }
  ],
  "recommendation": "建议优先补充 SQL 项目描述和接口开发细节，再考虑 Redis/Docker 加分项。"
}
```

这部分非常适合向量组员负责，因为它连接了：

- 岗位知识库
- 技能词典
- 简历文本
- 多岗对比

## 推荐提交记录

建议拆成这些提交：

```text
feat(rag): 增加知识库文档加载器
feat(rag): 支持岗位画像和技能词典索引
feat(matching): 增加匹配结果知识引用
feat(matching): 输出核心技能与加分技能缺口
feat(compare): 增加多岗位共同能力缺口分析
test(rag): 增加知识库加载与检索测试
```

如果时间紧，可以减少为 3 条：

```text
feat(rag): 接入岗位画像和技能词典知识库
feat(matching): 增加知识引用和技能缺口分层
test(rag): 增加知识库检索测试
```

## 最低完成线

如果今天时间不够，最低完成这三项就很好：

1. 新增 `rag_knowledge_loader.py`，统一加载岗位画像和技能词典。
2. 匹配结果增加 `references`，说明系统参考了什么知识。
3. 技能缺口分为核心缺口和加分缺口。

这三项最能体现“知识库不是摆设”，也最符合向量库组员的职责。

## 验收方式

建议她完成后至少验证这些场景：

### 场景一：AI 应用开发工程师

输入目标岗位：

```text
AI应用开发工程师
```

期望结果：

- 系统识别方向为后端 / AI 应用开发。
- 后端、AI 应用开发相关岗位排在前面。
- 产品、运营、内容岗位不应高分排在前面。
- 匹配结果显示引用了岗位画像和技能词典。

### 场景二：后端开发实习生

输入目标岗位：

```text
Python后端开发实习生
```

期望结果：

- 命中 Python、接口开发、SQL 等核心能力。
- Redis、Docker、Linux 等作为加分缺口展示。
- 用户能看懂为什么这个岗位得分高。

### 场景三：多岗对比

选择 3 个后端 / AI 应用开发岗位进行对比。

期望结果：

- 能显示共同要求。
- 能显示共同缺口。
- 能给出简历修改优先级建议。

## 结论

向量库组员今天最有价值的工作，不是继续单独新增岗位或面试题，而是把已有知识材料变成用户可感知的匹配依据。

最推荐优先做：

1. 知识库文档加载器
2. 匹配结果知识引用
3. 核心技能 / 加分技能缺口分层
4. 多岗对比共同能力缺口总结

