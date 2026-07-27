"""端到端验证：真实 DeepSeek 模型下，evaluate_answer 对乱码/脏话/认真回答的处理。

重点验证用户诉求：
  1) 判定(相关性/合理性/乱码/脏话)交给 AI；
  2) 瞎说/脏话 -> 对应反馈 + 不追问；
  3) 反馈不死板(由 AI 生成，非固定模板)。

运行：backend\\venv\\Scripts\\python.exe scripts\\verify_live.py
（依赖 .env 中 LLM_PROVIDER=deepseek + LLM_API_KEY）
"""
import os
import sys

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)

from app.core.config import settings  # noqa: E402
from app.services.interview_agent import evaluate_answer, _llm_enabled  # noqa: E402

QUESTION = "请介绍你最有挑战的一个项目经历，你在其中承担了什么角色、解决了什么问题？"
POSITION = "后端开发工程师"
REQUIREMENTS = "熟悉 Python、FastAPI、Redis、高并发接口优化与稳定性保障"

CASES = [
    ("纯乱码", "萨达萨达"),
    ("键盘沙拉", "asdfghjkl qwertyuiop zxcvbnm"),
    ("脏话", "你这问题傻逼，我懒得答了"),
    ("敷衍", "随便写写，不知道写什么"),
    ("认真技术回答", "我在上个项目负责后端服务，用 Python 和 FastAPI 实现订单接口，通过 Redis 缓存把响应时间从 300ms 降到 50ms，提升了接口稳定性。"),
]


def main():
    print(f"llm_enabled={_llm_enabled()}  provider={settings.llm_provider}  model={settings.llm_model}")
    out = []
    for name, answer in CASES:
        state = {
            "questions": [QUESTION],
            "current_index": 0,
            "answers": [{}],
            "target_position": POSITION,
            "job_requirements": REQUIREMENTS,
            "interview_mode": "技术面",
        }
        res = evaluate_answer(state, answer)
        followup = res.get("followup_question")
        no_followup = followup is None
        out.append(
            f"\n■ {name}\n"
            f"  回答: {answer}\n"
            f"  分数: {res.get('score')}\n"
            f"  是否追问: {'否(无效拦截)' if no_followup else '是(正常追问)'}\n"
            f"  feedback(overall): {res.get('feedback')}\n"
            f"  issues: {res.get('issues')}\n"
            f"  improvement_suggestions: {res.get('improvement_suggestions')}\n"
        )
    text = "\n".join(out)
    result_path = os.path.join(BACKEND_DIR, "scripts", "verify_live_result.txt")
    with open(result_path, "w", encoding="utf-8") as f:
        f.write(text)
    try:
        print(text)
    except UnicodeEncodeError:
        print("[控制台编码受限，完整结果见 scripts/verify_live_result.txt]")
    print(f"\n结果已写入: {result_path}")


if __name__ == "__main__":
    main()
