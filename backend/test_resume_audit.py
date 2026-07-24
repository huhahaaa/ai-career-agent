"""简历审核模块 - 完整功能演示测试"""

import json
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from app.services.resume_audit import audit_resume_text, _find_vague_phrases, _find_biased_phrases, _has_quantifier

# ── 3份不同质量的简历 ──

resume_excellent = """王伟，2023年毕业于北京大学软件工程专业，硕士学历，GPA 3.9/4.0。
技能：React、Vue3、TypeScript、Node.js、Go、Kubernetes、AWS、MySQL、Redis、GraphQL。

项目经历：
1. 企业级微前端平台（2022.03-2023.06）：担任核心开发，基于qiankun构建微前端架构，整合8个独立子应用。引入Module Federation实现按需加载，首屏加载时间从6.3秒降至1.8秒（降低71%），单应用构建时间从120秒降至35秒。支持50+开发者并行开发，系统上线后承载日均50万PV。
2. 低代码表单引擎（2021.09-2022.02）：从零搭建，使用React+TypeScript开发渲染引擎，支持20+种字段类型的拖拽配置和联动校验。自定义DSL解析器处理嵌套表单和条件渲染，编写单元测试覆盖率92%。被公司内部3个业务线采用，减少表单开发工作量约60%。
3. 开源贡献：给Ant Design提交PR 5个（已合并），修复Table组件虚拟滚动bug和Form组件性能问题。个人GitHub 800+ stars。

实习经历：2022.06-2022.09 字节跳动前端实习生，负责抖音创作者平台的数据看板模块，使用React+ECharts实现多维数据可视化，支持10+种图表类型的动态切换和导出。"""

resume_mediocre = """李明，2024年毕业，本科学历，计算机相关专业。
技能：了解HTML、CSS、JavaScript，熟悉React和Vue。

项目经历：
1. 课程设计-学生管理系统：参与了前端开发工作，主要负责相关页面的代码编写，使用Vue框架。配合后端完成了数据展示功能，具有一定程度的项目经验。
2. 仿淘宝首页：自己练手做的一个静态页面，熟悉了CSS布局和响应式设计，能实现基本的页面效果。

实习经历：在某小公司实习了2个月，协助同事做一些页面修改，帮忙测试和修复bug。

自我评价：学习能力强，对前端开发有热情，希望能在实际工作中成长。"""

resume_risky = """赵刚，资深前端专家，业内顶尖水平。

精通所有前端框架，包括React、Vue、Angular、Svelte、Solid.js，完全负责过多个千万级用户项目。
技能：精通所有主流技术栈，全权负责系统架构设计，技术能力无人能及。

项目经历：
1. 完全负责某大型电商平台前端重构，最优秀的架构设计方案，性能达到业内顶尖水平。
2. 全权负责公司核心产品从零到一的开发，做出了最优秀的用户体验。

实习经历：无

教育背景：某大学（辍学）

自我评价：我是业内最优秀的前端工程师之一，技术能力无人能及，任何技术问题都能快速解决。"""


def test_resume(name, resume_text, target):
    """测试一份简历的审核"""
    print("=" * 70)
    print(f"  {name}")
    print("=" * 70)

    # 规则层检测
    vague = _find_vague_phrases(resume_text)
    biased = _find_biased_phrases(resume_text)
    has_quant = _has_quantifier(resume_text)

    print(f"\n  [规则层 快速扫描]")
    if vague:
        print(f"    空泛表达: {vague}")
    else:
        print(f"    空泛表达: 无")
    if biased:
        print(f"    夸大风险: {biased}")
    else:
        print(f"    夸大风险: 无")
    print(f"    含量化数据: {'是' if has_quant else '否'}")

    rule_score = 100 - len(vague) * 5 - len(biased) * 10
    print(f"    规则评分(30%权重): {rule_score}/100")

    # LLM 深度审核
    print(f"\n  [LLM 深度分析] 分析中...")
    result = audit_resume_text(resume_text, target)

    print(f"\n  ── 审核结果 ──")
    print(f"  综合评分: {result['score']}/100")
    print(f"  风险等级: >>> {result['risk_level']} <<<")

    if result['risk_flags']:
        print(f"\n  发现 {len(result['risk_flags'])} 个风险点:")
        for i, flag in enumerate(result['risk_flags'], 1):
            print(f"    {i}. {flag}")
    else:
        print(f"\n  未发现风险点")

    if result['missing_keywords']:
        print(f"\n  缺失关键词: {result['missing_keywords']}")

    if result['suggestions']:
        print(f"\n  改进建议 ({len(result['suggestions'])}条):")
        for i, sug in enumerate(result['suggestions'], 1):
            print(f"    {i}. {sug[:120]}{'...' if len(str(sug)) > 120 else ''}")

    return result


# ── 主流程 ──

print("=" * 70)
print("           简历审核模块 - 完整功能演示")
print("=" * 70)
print()
print("测试 3 份不同质量简历: 优秀/中等/高风险")
print("检测维度: 技能-项目匹配、量化数据、一致性、夸大风险、个人贡献、字段缺失")
print("评分机制: 规则层(30%) + LLM深度分析(70%)")
print()

results = {}

# 测试 1: 优秀简历
results['优秀简历'] = test_resume(
    "测试 1: 优秀简历 (王伟 - 硕士, 大厂实习, 量化数据完整)",
    resume_excellent,
    "高级前端开发工程师"
)

print()
print()

# 测试 2: 中等简历
results['中等简历'] = test_resume(
    "测试 2: 中等简历 (李明 - 本科, 经历薄弱, 空泛表达多)",
    resume_mediocre,
    "前端开发工程师"
)

print()
print()

# 测试 3: 高风险简历
results['高风险简历'] = test_resume(
    "测试 3: 高风险简历 (赵刚 - 夸大表述, 缺教育/实习)",
    resume_risky,
    "前端开发工程师"
)

# ── 汇总 ──
print()
print("=" * 70)
print("                    对比汇总")
print("=" * 70)
print()
print(f"  {'简历':<16} {'综合评分':<10} {'风险等级':<8} {'风险点数':<8}")
print(f"  {'-'*50}")
for name, r in results.items():
    print(f"  {name:<16} {r['score']:<10} {r['risk_level']:<8} {len(r['risk_flags']):<8}")

print(f"\n{'=' * 70}")
print(f"                    简历审核测试完成!")
print(f"{'=' * 70}")
