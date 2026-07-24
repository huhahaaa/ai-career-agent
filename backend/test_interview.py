"""面试 Agent 完整流程测试脚本"""

import json
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from app.services.interview_agent import start_interview, evaluate_answer, finish_interview

# 模拟简历
resume = """张三，2024年毕业于某大学计算机专业。
技能：Python、React、TypeScript、MySQL、Git。
项目经历：
1. 电商后台管理系统：使用React+Python开发，负责订单模块，用户操作响应时间减少40%。
2. 个人博客：使用Vue+Node.js搭建，访问量月均3000+。
实习经历：在某科技公司担任前端实习生3个月，参与公司官网改版。"""

print("=" * 60)
print("测试 1: 开始面试")
print("=" * 60)
try:
    result = start_interview(resume, "前端开发工程师")
    session_id = result["session_id"]
    print(f"Session ID: {session_id}")
    print(f"题目总数: {result['total_questions']}")
    print(f"工具调用: {result['tools_used']}")
    print(f"第1题: {result['question'][:80]}...")
    print("OK")
except Exception as e:
    print(f"失败: {e}")

print()
print("=" * 60)
print("测试 2: 短回答（应触发追问）")
print("=" * 60)
try:
    a1 = evaluate_answer(session_id, "我会React，做了几个项目")
    print(f"追问触发: {a1.get('is_followup')}")
    if a1.get('is_followup'):
        print(f"追问内容: {a1.get('followup_question', '')[:80]}...")
    print("OK")
except Exception as e:
    print(f"失败: {e}")

print()
print("=" * 60)
print("测试 3: 补充回答（应打分并推进）")
print("=" * 60)
try:
    a2 = evaluate_answer(session_id, "我用React和TypeScript开发了电商后台的订单模块，通过引入虚拟列表和懒加载，将订单列表页首屏加载时间从5秒优化到1.5秒，用户操作响应时间减少了40%。")
    print(f"是否追问: {a2.get('is_followup')}")
    print(f"总分: {a2.get('score')}")
    if a2.get('dimension_scores'):
        dim = a2['dimension_scores']
        print(f"  内容相关性: {dim.get('content_relevance', 'N/A')}")
        print(f"  专业知识: {dim.get('professional_accuracy', 'N/A')}")
        print(f"  表达清晰度: {dim.get('clarity', 'N/A')}")
        print(f"  STAR完整性: {dim.get('star_completeness', 'N/A')}")
        print(f"  岗位匹配度: {dim.get('position_match', 'N/A')}")
    print(f"下一题: {(a2.get('next_question') or '无(面试结束)')[:80]}...")
    print("OK")
except Exception as e:
    print(f"失败: {e}")

print()
print("=" * 60)
print("测试 4: 简历审核")
print("=" * 60)
try:
    from app.services.resume_audit import audit_resume_text
    audit_result = audit_resume_text(resume, "前端开发工程师")
    print(f"综合评分: {audit_result['score']}")
    print(f"风险等级: {audit_result['risk_level']}")
    print(f"风险标记数: {len(audit_result['risk_flags'])}")
    print(f"建议数: {len(audit_result['suggestions'])}")
    print(f"缺失关键词: {audit_result.get('missing_keywords', [])}")
    print("OK")
except Exception as e:
    print(f"失败: {e}")

print()
print("完成!")
