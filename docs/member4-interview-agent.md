# 4 号成员 · 简历审核与面试 Agent · 第二天工作说明

> 角色：4 号（简历审核与面试 Agent）
> 对应任务：总体项目书「项目 7：AI 面试陪练、简历优化与岗位匹配 Agent」+ 第二天任务书（Agent 成员部分）
> 模块位置：`backend/app/services/interview_agent.py`、`backend/app/services/resume_audit.py`、`data/interview_question_bank.json`

---

## 一、第二天任务完成对照（任务书验收点）

| 任务书要求 | 实现位置 | 状态 |
| --- | --- | --- |
| 面试 Agent 拆成多种模式（HR面 / 技术面 / 压力面 / 反馈教练） | `INTERVIEW_MODES` + `INTERVIEW_MODE_PROMPTS` | ✅ 已具备 |
| 优化 Prompt，要求 Agent 不输出 Markdown 符号 | `_strip_markdown`（去除 `**`、`# `、`` ` `` 等） | ✅ 已具备并增强 |
| 优化评分反馈结构：得分 / 优点 / 问题 / 改进建议 | `InterviewAnswerResult`（strengths / issues / improvement_suggestions） | ✅ 已具备 |
| 整理 30 个面试题库 JSON，按岗位或题型分类 | `data/interview_question_bank.json` | ✅ 已具备并扩展 |
| 增加低质量回答、回答过短和信息不足时的测试案例 | `tests/test_interview_api.py` | ✅ 新增并修复 |

接口/页面可切换面试模式、评分结构化、STAR 建议不再输出未渲染 Markdown——均满足验收。

---

## 二、本轮「缺陷修复」记录（发现问题 → 解决）

1. **题库从未被加载（真实缺陷）**
   - 现象：`load_question_bank` 路径写成 `Path(__file__).resolve().parents[4] / "data"`，指向仓库外的 `Desktop/data`，导致题库永远加载失败，报告中的 `question_bank_summary.total` 恒为 0。
   - 修复：改为 `parents[3]`（项目根），与 `scripts/` 中的 `parents[2]` 约定一致。现 `get_question_bank_summary()` 可正确返回 30 题统计。

2. **测试文件重复定义（缺陷）**
   - 现象：`tests/test_interview_api.py` 中同一批测试函数被定义两遍（后定义覆盖前定义），pytest 只跑一份，文件冗余易错。
   - 修复：重写为单份干净测试套件（20 个用例），并修正原先写死阈值（如 `<50`）导致 mock 下不稳定的断言。

3. **夸大表达识别误报（自测发现）**
   - 现象：空泛/夸大词表含「第一」「最」，会把追问前缀「第一轮回答」误判为夸大表达。
   - 修复：移除易误报的短词，仅保留「绝对 / 完美 / 100% / 完全 / 肯定 / 一定 / 唯一 / 没有缺点 / 精通一切 / 无人能及 / 天下第一」等明确绝对化表述。

---

## 三、本轮「Agent 丰富化」内容（老师说重点是 Agent，参考两份任务书）

在组长已有基础上，针对总体项目书「项目 7」的**基本要求 #14 / #15** 与**进阶要求 #2** 做了增强：

### 1. 岗位感知出题（需求 #14：按岗位生成不同题库）
- 题库新增 `positions` 字段，30 道题按适用岗位标注（前端 / 后端 / 产品 / 运营 / 算法 / 数媒）。
- 新增 `position_banks`：为 6 类岗位各提供专属面试题（前端重 reflow/工程化、后端重索引/事务/限流、产品重需求优先级、运营重 ROI/漏斗、算法重模型评估、数媒重创作工具链与交互设计）。
- `start_interview` 现在会根据 `target_position` 自动选用对应岗位题库（识别支持中英文/别称，如 "frontend"、"数字媒体" → 数媒）。

### 2. 空泛 / 夸大表达识别（需求 #15：识别空泛表达、项目不清晰和经历夸大风险）
- 新增 `_detect_expression_risks`：识别空泛词（一些 / 比较好 / 差不多 / 还可以…）与夸大绝对化词。
- 命中后自动在评分反馈的「问题」与「改进建议」中追加提示，并降低对应维度分（空泛 → 表达清晰度；夸大 → 专业准确性）。
- 返回 `vague_flags` / `biased_flags`，前端可高亮展示。

### 3. 评分校准（进阶 #2：对比 Agent 评分、规则评分和人工评分）
- 每题评分同时输出 `llm_score`（Agent/LLM 评分，仅启用 LLM 时存在）与 `rule_score`（纯规则评分基线）。
- 终报告新增 `calibration_summary`：汇总 Agent 平均分、规则平均分、LLM 样本数、空泛/夸大标记数，便于评估 Agent 稳定性，并为后续接入人工评分做对照。

---

## 四、面试题库数据说明（交付物：可在报告中作为「面试题库数据」）

文件：`data/interview_question_bank.json`

结构：
```json
{
  "meta": { "total_questions": 30, "position_bank_count": 6, "modes": [...], "positions": [...] },
  "questions": [ { "id", "mode", "category", "positions", "question", "difficulty", "expected_focus" } ],
  "position_banks": { "前端": [...], "后端": [...], "产品": [...], "运营": [...], "算法": [...], "数媒": [...] }
}
```

运行时统计（通过 `/interview/finish` 报告或 `get_question_bank_summary()` 获取）：
- 通用题库：**30 题**，覆盖 HR面 / 技术面 / 压力面 / 反馈教练 4 种模式、8 类题型。
- 岗位题库：**6 个岗位**，每岗位 7~8 道专属题。
- 按岗位标注分布（30 题累计，单题可标注多岗位）：前端 30 · 后端 30 · 算法 28 · 数媒 27 · 产品 22 · 运营 19。

---

## 五、测试覆盖（任务书第 5 条：低质量 / 过短 / 信息不足）

`tests/test_interview_api.py`（mock 兜底，无需 API Key，可独立运行）：
- 低质量 / 过短回答：`test_short_answer_triggers_followup`、`test_low_quality_answer_is_scored_low_or_flagged`、`test_empty_or_whitespace_answer_triggers_followup`、`test_consecutive_low_quality_answers_still_scored`。
- 信息不足 / 空泛表达：`test_information_insufficient_answer_flags_vague_expression`、`test_vague_phrase_detection`、`test_biased_phrase_not_false_positive_on_normal_words`、`test_biased_phrase_detection`。
- 岗位维度：`test_frontend_position_uses_position_bank`、`test_backend_position_uses_position_bank`、`test_position_normalization`。
- 评分校准：`test_finish_interview_returns_calibration_summary`。
- 模式与去 Markdown：`test_interview_mode_generates_mode_specific_first_question`、`test_strip_markdown_removes_symbols` 等。

运行：`cd backend && python -m pytest tests/test_interview_api.py -q`（注：仓库 pytest 需先安装依赖；本机若无 `email-validator` 等依赖，可用 `--noconftest` 单独跑本单元测试）。

---

## 六、建议提交清单（满足 7~9 条有效提交）

1. fix(interview): 修正题库加载路径 parents[4]→parents[3]
2. test(interview): 清理重复测试函数并修正 mock 下不稳定断言
3. data(bank): 30 题新增 positions 字段
4. data(bank): 新增 6 岗位专属题库 position_banks
5. feat(interview): 岗位感知出题 + _normalize_position
6. feat(interview): 空泛/夸大表达识别（需求 #15）
7. feat(interview): 评分校准 llm_score/rule_score + calibration_summary（进阶 #2）
8. test(interview): 补充岗位/空泛/校准用例
9. docs: 4 号成员第二天日报与面试 Agent 模块说明

> 说明：组长 `main` 已包含面试 Agent 的基础实现（多模式、去 Markdown、结构化评分）。上述 1~9 为在组长架构上，由 4 号成员针对「缺陷修复 + Agent 丰富化（岗位题库 / 表达风险 / 评分校准）」独立完成的增量工作，建议以 4 号成员账号提交。

---

## 七、简历审核 Agent 丰富化（本轮同日完成）

老师强调重点是 **agent 部分**。在面试 Agent 丰富化之后，对「简历审核 Agent」（`backend/app/services/resume_audit.py`）做同等力度的补强，对齐开发计划阶段 3 要求的四类风险：**模糊表达 / 关键词缺失 / 项目描述不完整 / 夸大风险**。

### 7.1 需求对照（阶段 3）
| 阶段 3 要求 | 实现 |
| --- | --- |
| 模糊表达 | `VAGUE_PHRASES` 词表 + `_detect_expression_risks`，命中即标记并在清晰度维度扣分 |
| 关键词缺失 | `POSITION_REQUIRED_KEYWORDS` 六岗位专属关键词库 + `_missing_keywords`，无 LLM 也生效 |
| 项目描述不完整 | `_split_projects` + `_assess_project_quality`：检查个人职责 / 量化结果，缺失则标记 |
| 夸大风险 | `BIASED_PHRASES` 词表（如「完美/绝对/100%/最优秀」），命中即标记 |

### 7.2 Agent 能力增强（与面试 Agent 对齐）
- **岗位感知（position-aware）**：复用面试 Agent 的 `_normalize_position` / `DEFAULT_POSITIONS`，按目标岗位做匹配度评分与关键词缺失检测。
- **结构化五维评分**：`completeness` 完整度 / `position_match` 岗位匹配 / `quantification` 量化 / `clarity` 表达 / `project_quality` 项目质量（满分 100，规则可解释）。
- **字段检测**：`_detect_resume_fields` 检测邮箱/手机/教育/经历/项目/技能/作品集七类必备字段并展示缺失项。
- **评分校准（rule vs llm，进阶 #2 同思路）**：保留 `rule_score`（纯规则基线）与 `llm_score`（LLM 深度审核分，离线时为 `None`），便于对照。
- **LLM 深度审核**：`_llm_deep_audit` 让大模型返回维度分 + 缺失关键词 + 建议，失败自动回退规则，保证离线可用。

### 7.3 schema / 接口
- `ResumeAuditResult` 新增：`dimension_scores`、`rule_score`、`llm_score`、`detected_fields`、`position_bucket`。
- 仅扩展响应字段，**未改动 `ResumeAuditReport` 数据库列**，无需迁移。

### 7.4 测试
- 新增 `backend/tests/test_resume_audit.py`：13 个用例（岗位归一化、字段检测、维度评分、强弱简历风险等级、关键词缺失、空泛/夸大命中、评分校准、项目质量），`--noconftest` 下全绿。

## 八、岗位题库接入前端面试页

把后端已有的「岗位专属题库」能力真正连到 UI，让用户在面试页选择岗位与模式。

### 8.1 前端 `MockInterview.jsx`
- 目标岗位由自由文本输入改为 **岗位下拉**（前端/后端/产品/运营/算法/数媒），提示「选择岗位后从对应岗位专属题库出题」。
- 新增 **面试模式下拉**（技术面/HR面/压力面/反馈教练），传入 `startInterview`。
- 顶部展示「岗位 · 模式」。

### 8.2 `client.js`
- `startInterview` 新增 `interviewMode` 参数，POST 时发送 `interview_mode`。
- mock 兜底按「岗位 + 模式」生成首题（位置感知）。
- 新增 `auditResume({resumeText, targetPosition, resumeId})`，对接简历审核接口，并提供结构化 mock 兜底。

### 8.3 后端联动
- 面试接口 `start_interview` 返回新增 `position_bucket`，`InterviewQuestion` schema 同步增加该字段，前端可确认已命中岗位题库。

### 8.4 简历审核页接入真实 Agent
- `ResumeReview.jsx` 重构为：粘贴/带入简历文本 + 选择岗位 → 点击「运行简历审核 Agent」→ 渲染五维评分柱状图、字段检测、风险标记、缺失关键词、改进建议、规则/LLM 校准分。
- 从上传页带 `resumeId` 进入时自动拉取简历内容预填。
- 未运行审核时保留原有解析样例视图作为兜底。

## 九、真实岗位数据接入 Agent（24 家岗位，本轮补齐）

此前岗位关键词库与面试出题依赖硬编码/小题库。现将 `data/processed/jobs_clean.jsonl`（24 条已清洗岗位、6 大类）真正接入两个 Agent，做到「数据驱动」。

### 9.1 新增 `backend/app/services/job_data.py`（数据加载与派生，零 LLM 依赖）
- `load_jobs()`：加载 24 条岗位（带内存缓存），字段为 `source_id / category / title / skills / responsibilities / requirements` 等。
- `CATEGORY_TO_POSITION`：6 大类 → 6 岗位桶（前端开发→前端、后端开发→后端、产品经理→产品、运营→运营、数字媒体/内容→数媒、算法/机器学习→算法），与 `DEFAULT_POSITIONS` 1:1 对应。
- `derive_position_keywords(bucket)`：**自动派生**关键词库——按岗位 `skills` 字段出现频次取 Top-12，干净可解释；数据缺失/缺桶时回退 `FALLBACK_KEYWORDS`。
- `get_position_job_summary(bucket, job_id)`：生成可引用的真实岗位画像（职责/要求/高频技能），用于面试岗位要求分析与出题提示。
- `get_position_responsibilities(bucket, job_id)`：返回真实职责片段，用于把真实岗位职责融入面试题。
- `get_job_by_id(source_id)`：按真实岗位编号精确取一条，供 `start_interview(target_job_id=)` 聚焦特定岗位。

### 9.2 `resume_audit.py` 关键词库数据化
- `POSITION_REQUIRED_KEYWORDS` 由「硬编码六岗位表」改为 `{**FALLBACK_KEYWORDS, **derive_all_position_keywords()}`：优先使用真实岗位 `skills` 派生词（如前端含 React/TypeScript/Vue/AWS/LangChain…，算法含 JAX/PyTorch/RLHF/GRPO…），缺失时回退兜底，保证离线可用。

### 9.3 `interview_agent.py` 出题与要求分析引用真实数据
- `_analyze_job_requirements`：在 LLM 提示词与离线兜底文本中嵌入 `get_position_job_summary` 的真实职责/要求，使「岗位要求分析」基于真实 JD 而非泛泛而谈；新增 `job_id` 参数可聚焦具体岗位。
- `_generate_questions`：离线兜底题库以**真实岗位职责题为主**（最多 6 道），首题保留模式专属开场，不足 8 道用默认题补足并去重；同时修复了「离线时 fallback 被重复拼接导致题目翻倍」的历史缺陷。LLM 在线时把真实职责写入提示词，并仅用兜底题补全不足 8 道的部分。
- `start_interview` 透传 `target_job_id` 到上述两函数。

### 9.4 测试
- 新增 `backend/tests/test_job_data.py`：10 个用例（24 条加载、桶映射、编号查询、关键词派生、摘要/职责引用、审核关键词接入），`--noconftest` 全绿。
- 回归：简历审核 13 + 面试 20 + 岗位数据 10 = **43 用例全绿**；单接口全流程 start→evaluate→finish 跑通，题库 8 道、真实职责题占比过半且无重复。

## 十、本轮累计有效提交建议（含第七~九节，满足 7~9 条）
1. fix(interview): 修正题库加载路径 parents[4]→parents[3]
2. test(interview): 清理重复测试并修正断言
3. data(bank): 30 题加 positions + 6 岗位专属题库
4. feat(interview): 岗位感知出题
5. feat(interview): 空泛/夸大识别
6. feat(interview): 评分校准 llm_score/rule_score
7. feat(resume): 简历审核 Agent 丰富化（岗位感知 + 五维评分 + 四类风险 + 校准）
8. feat(frontend): 面试页岗位/模式下拉接岗位题库 + 简历审核页接真实 Agent
9. test(resume): 新增 13 个简历审核用例
10. feat(data): 新增 job_data.py，24 条真实岗位接入 Agent（关键词自动派生 + 出题/要求分析引用真实 JD）
11. fix(interview): 修复离线题库 fallback 被重复拼接导致题目翻倍
12. test(job_data): 新增 10 个岗位数据接入用例
13. docs: 4 号成员 Agent 模块说明（面试 + 简历 + 真实岗位数据）

> 同样建议以 4 号成员账号独立提交上述增量，勿将组长原代码计入自身 commit。
