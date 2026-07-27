"""端到端验证面试官 agent 的重构效果（真实 DeepSeek）：

1. 问题多样化：同一岗位不同模式、不同岗位的开场/题目是否不再雷同；
2. 互动：乱码 -> 对应反馈 + 不追问；正常回答 -> 变化反馈 + 过渡语 + 下一题/自然追问；
3. 判定：乱码/脏话给低分且对应反馈，认真回答正常评分。

运行：backend\\venv\\Scripts\\python.exe scripts\\verify_interview_flow.py
"""
import os
import sys

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)
sys.stdout.reconfigure(encoding="utf-8")

from app.services.interview_agent import start_interview, evaluate_answer, _llm_enabled  # noqa: E402

RESUME = (
    "张三，3 年后端开发经验。主导过电商订单系统，用 Python/FastAPI 实现核心接口，"
    "通过 Redis 缓存与异步队列把高峰期接口响应从 300ms 降到 60ms，QPS 提升 4 倍。"
)


def show_questions(label, resume, position, mode):
    print(f"\n===== {label} =====")
    result = start_interview(resume_text=resume, target_position=position, interview_mode=mode)
    state = result["agent_state"]
    for i, q in enumerate(state["questions"], 1):
        print(f"  {i}. {q}")
    return state


def main():
    print(f"llm_enabled={_llm_enabled()}")
    show_questions("后端 / 技术面", RESUME, "后端", "技术面")
    show_questions("后端 / HR面", RESUME, "后端", "HR面")
    show_questions("产品 / 技术面", RESUME, "产品", "技术面")

    # 互动 + 判定
    print("\n===== 互动 & 判定（后端/技术面）=====")
    result = start_interview(resume_text=RESUME, target_position="后端", interview_mode="技术面")
    state = result["agent_state"]
    q0 = state["questions"][0]
    print(f"\n第1题: {q0}")

    gib = evaluate_answer(state, "萨达萨达")
    print(f"\n[乱码回答] 追问={gib.get('followup_question')} 分数={gib.get('score')}")
    print(f"  反馈: {gib.get('feedback')}")
    print(f"  下一题: {gib.get('next_question')}")

    # 用与第1题相关的认真回答再测一轮（避免答非所问干扰）
    state2 = start_interview(resume_text=RESUME, target_position="后端", interview_mode="技术面")["agent_state"]
    q0b = state2["questions"][0]
    print(f"\n第1题: {q0b}")
    good = evaluate_answer(
        state2,
        f"关于“{q0b[:20]}”：我去年负责订单服务的稳定性，遇到晚高峰接口超时。我先用 Redis 缓存热点数据，"
        "再把慢接口拆成异步，把响应从 300ms 降到 60ms，超时率从 5% 降到 0.3%，我主导了这次改造。",
    )
    print(f"\n[认真回答] 追问={good.get('followup_question')} 分数={good.get('score')}")
    print(f"  反馈: {good.get('feedback')}")
    print(f"  优点: {good.get('strengths')}")
    print(f"  下一题: {good.get('next_question')}")


if __name__ == "__main__":
    main()
