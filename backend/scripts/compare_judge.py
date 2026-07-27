"""对比 mock 与真实 DeepSeek 在面试回答检定（尤其乱码/脏话/跑题）上的 verdict 与反馈差异。

用法：
    backend\\venv\\Scripts\\python.exe scripts\\compare_judge.py
    # 需要真实模型时通过环境变量传入 Key：
    set DEEPSEEK_KEY=sk-xxxx && backend\\venv\\Scripts\\python.exe scripts\\compare_judge.py

同一进程内分别切换 settings.llm_provider 跑两轮，输出并排对比表到 result 文件（UTF-8）。
"""
import os
import sys

# 让脚本能 import app 包（脚本位于 backend/scripts 下）。
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)

from app.core.config import settings  # noqa: E402
import app.services.answer_quality as aq  # noqa: E402
from app.services.answer_quality import judge_answer_quality  # noqa: E402
from app.services.interview_agent import _score_answer  # noqa: E402

QUESTION = "请介绍你最有挑战的一个项目经历，你在其中承担了什么角色、解决了什么问题？"
POSITION = "后端开发工程师"
REQUIREMENTS = "熟悉 Python、FastAPI、Redis、高并发接口优化与稳定性保障"
MODE = "技术面试"

# 覆盖：纯乱码、键盘沙拉、脏话、敷衍、含键盘行示例的认真回答、纯技术认真回答、跑题
CASES = [
    ("纯乱码(萨达萨达)", "萨达萨达"),
    ("键盘沙拉长串", "asdfghjkl qwertyuiop zxcvbnm lkjhgfdsa"),
    ("脏话", "你这问题傻逼，我懒得答了"),
    ("敷衍非作答", "随便写写，不知道写什么"),
    ("认真(含asd/qwe/zxc举例)", "我用 qwe 和 asd 举例说明：项目里通过 React 和 FastAPI 搭建了高并发接口，QPS 从 200 优化到 2000，我负责核心模块重构。"),
    ("认真技术回答", "我在上个项目负责后端服务，用 Python 和 FastAPI 实现订单接口，通过 Redis 缓存把响应时间从 300ms 降到 50ms，提升了接口稳定性。"),
    ("跑题", "今天天气真好，我去吃了火锅，然后睡了一下午。"),
]


def run_mode(mode: str, api_key: str):
    if mode == "mock":
        settings.llm_provider = "mock"
        settings.llm_api_key = ""
    else:
        settings.llm_provider = "deepseek"
        settings.llm_api_key = api_key
        # 2026 起 deepseek-chat 已下线，端点只接受 deepseek-v4-pro / deepseek-v4-flash
        settings.llm_model = os.environ.get("DEEPSEEK_MODEL", "deepseek-v4-flash")
    aq._client = None  # 重置缓存的 OpenAI client，避免复用 mock 态

    rows = []
    for name, answer in CASES:
        verdict = judge_answer_quality(QUESTION, answer, POSITION, REQUIREMENTS, MODE)
        scores = _score_answer(QUESTION, answer, POSITION, REQUIREMENTS, MODE, verdict=verdict)
        rows.append({
            "name": name,
            "answer": answer,
            "verdict": verdict,
            "total": scores.get("total"),
            "feedback": {
                "strengths": scores.get("strengths", ""),
                "issues": scores.get("issues", ""),
                "improvement_suggestions": scores.get("improvement_suggestions", ""),
                "overall_comment": scores.get("overall_comment", ""),
            },
        })
    return rows


def render(rows, mode: str) -> str:
    lines = [f"===== {mode.upper()} 模式 ====="]
    for r in rows:
        v = r["verdict"]
        lines.append(f"\n■ {r['name']}")
        lines.append(f"  回答: {r['answer']}")
        lines.append(
            f"  verdict: valid={v.valid} category={v.category} "
            f"gibberish={v.gibberish} abuse={v.abuse} "
            f"relevance={v.relevance} coherence={v.coherence} llm_used={v.llm_used}"
        )
        lines.append(f"  总分: {r['total']}")
        fb = r["feedback"]
        lines.append(f"  strengths: {fb['strengths']}")
        lines.append(f"  issues: {fb['issues']}")
        lines.append(f"  improvement_suggestions: {fb['improvement_suggestions']}")
        lines.append(f"  overall_comment: {fb['overall_comment']}")
    return "\n".join(lines)


def main():
    # 优先用命令行传入的 DEEPSEEK_KEY；否则回退到 .env 中已配置的 LLM_API_KEY（避免 Key 进入聊天记录）。
    key = os.environ.get("DEEPSEEK_KEY", "").strip() or settings.llm_api_key.strip()
    mock_rows = run_mode("mock", "")
    out = [render(mock_rows, "mock")]

    if key:
        real_rows = run_mode("real", key)
        out.append(render(real_rows, "real"))
        # 并排差异摘要
        out.append("\n===== 差异摘要（mock → real）=====")
        for (m, real) in zip(mock_rows, real_rows):
            mv, rv = m["verdict"], real["verdict"]
            diffs = []
            if mv.category != rv.category:
                diffs.append(f"category {mv.category}→{rv.category}")
            if mv.valid != rv.valid:
                diffs.append(f"valid {mv.valid}→{rv.valid}")
            if mv.gibberish != rv.gibberish:
                diffs.append(f"gibberish {mv.gibberish}→{rv.gibberish}")
            if mv.abuse != rv.abuse:
                diffs.append(f"abuse {mv.abuse}→{rv.abuse}")
            if m["total"] != real["total"]:
                diffs.append(f"total {m['total']}→{real['total']}")
            if m["feedback"]["issues"] != real["feedback"]["issues"]:
                diffs.append("issues 文案不同")
            tag = " | ".join(diffs) if diffs else "一致"
            out.append(f"  - {m['name']}: {tag}")
    else:
        out.append("\n[未提供 DEEPSEEK_KEY，仅运行 mock 模式。]")

    text = "\n".join(out)
    result_path = os.path.join(BACKEND_DIR, "scripts", "compare_result.txt")
    with open(result_path, "w", encoding="utf-8") as f:
        f.write(text)
    # 控制台也输出（Windows GBK 可能乱码，详见 compare_result.txt）
    try:
        print(text)
    except UnicodeEncodeError:
        print("[控制台编码受限，完整结果见 scripts/compare_result.txt]")
    print(f"\n结果已写入: {result_path}")


if __name__ == "__main__":
    main()
