"""完整面试流程测试：8题 → finish → 报告（长回答版本）"""

import json
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from app.services.interview_agent import start_interview, evaluate_answer, finish_interview

resume = """张三，2024年毕业于某大学计算机科学与技术专业，GPA 3.7/4.0。
技能：Python、React、TypeScript、MySQL、Git、Docker、Redis。
项目经历：
1. 电商后台管理系统（2023.06-2023.12）：担任前端负责人，使用React+TypeScript+Ant Design开发，负责订单模块和权限管理模块。项目上线后支撑日均2000+订单处理，首屏加载从4.2秒优化到1.1秒，用户操作响应时间平均减少45%。
2. 个人技术博客（2023.01-至今）：使用Vue3+Node.js+MySQL搭建全栈博客系统，实现文章管理、评论系统、标签分类和全文搜索。月均UV 3500+，SEO评分95分。部署在阿里云ECS，使用Docker容器化。
3. 校园二手交易小程序：使用微信小程序原生框架+云开发，负责商品发布、搜索和聊天模块，上线3个月累计用户1200+，交易完成率78%。
实习经历：2024.01-2024.04 在某互联网公司担任前端开发实习生，参与公司内部CMS系统的重构，独立负责富文本编辑器模块，使用Slate.js开发，支持图文混排、拖拽排序和实时协同编辑。"""

# 8个高质量长回答
answers = [
    # 第1题：自我介绍（210字）
    "我叫张三，2024年毕业于计算机专业，GPA 3.7。大学期间主导了三个项目：电商后台系统是我最骄傲的，作为前端负责人用React+TypeScript开发，将首屏从4.2秒优化到1.1秒。还独立搭建了个人技术博客，月访问量3500+，用Docker部署。实习期间用Slate.js从零做了一个富文本编辑器，支持实时协同。我的优势是技术栈比较全面，从React全家桶到Node.js到Docker都有实际经验，而且每个项目都有可量化的成果。我对前端开发是真心喜欢，不是应付找工作那种喜欢。",

    # 第2题：职业规划（190字）
    "短期1-2年，我希望在一家有技术氛围的公司深耕前端，把React生态吃透，同时补齐工程化方面的短板，比如CI/CD流程、性能监控体系、前端安全这些。中期3-5年，我想往全栈或前端架构方向发展，不满足于只写页面，要能理解整个系统的数据流和业务逻辑，做出技术选型和架构决策。长期来看，我希望把自己踩过的坑和沉淀的方法论输出成文章或分享，帮助更多前端新人成长。不过这些都是规划，我更看重的是每一步都走扎实，而不是急着升title。",

    # 第3题：项目深挖（280字）
    "电商后台让我成长最大。技术上，我主导了前端架构设计，用React Hooks做状态管理，TypeScript做类型约束。最大的挑战是订单列表页性能问题——列表超过500条时滚动严重掉帧。我先用Chrome Performance面板定位到是每次渲染都在重新创建组件实例，没有做虚拟化。对比了react-window和react-virtualized后选了前者，因为API更简洁、包体积小30%。封装了一个通用VirtualTable组件，把传入列配置和数据的逻辑抽离出来，其他页面也能复用。还有一个坑是状态管理——订单有10+种状态，页面间流转时状态同步容易乱。我用useReducer+Context做了全局订单状态机，定义了严格的状态转移规则，避免了非法切换。上线后列表页渲染时间从2.8秒降到180毫秒，日均2000+订单稳定运行。最遗憾的是没时间写单元测试——现在回想起来，有状态机逻辑的地方是最该写测试的。",

    # 第4题：技术难点（250字）
    "最难的是富文本编辑器的实时协同功能。实习时做的CMS编辑器需要支持多人同时编辑同一篇文档，而且不能有冲突导致内容丢失。我调研了OT（Operational Transformation）和CRDT两种方案，最终选OT——因为我们场景是中心化服务器，OT更成熟。具体实现上用了ShareDB做协同后端，前端在Slate.js基础上封装了操作转换层。核心难点是光标同步——多个人在同一个段落编辑时，光标位置会漂移。我通过在每次远程操作到来时重新计算相对偏移量解决了这个问题。另外网络断线重连后的状态恢复也很棘手，我参考了CKEditor的做法，在客户端维护操作日志队列，重连后批量回放未同步的操作。这个功能上线后支持了3人同时编辑无冲突，评测结果比旧系统效率提升60%。虽然我只负责前端部分，但这个过程让我理解了协同编辑的底层原理，比单纯写页面有意思多了。",

    # 第5题：技术基础——虚拟DOM（220字）
    "虚拟DOM本质是JS对象，用来描述真实DOM结构。React每次setState不会直接操作DOM，而是先在内存里生成新的虚拟DOM树，然后和旧的Diff比较，算出最小变更集合，最后一次性批量更新真实DOM。Diff算法有三层优化：tree diff只比较同层级节点，因为跨层级移动很少见；component diff对同一类型组件继续递归比较，不同类型直接替换整个子树；element diff通过key来识别节点的增删移动。性能提升的核心就是避免不必要的DOM操作。比如我们电商后台的列表，如果每新增一个订单就全量渲染，300条数据可能触发上万次DOM操作。用了虚拟DOM+key优化后，只新增必要的节点，性能差距是数量级的。不过虚拟DOM不是万能药——大规模数据还是得配合虚拟列表，两者结合才能真正解决长列表问题。",

    # 第6题：技术基础——异步（200字）
    "我用async/await处理异步请求，核心优势是代码看起来像同步的，方便错误处理。通常我会封装一个request工具函数，用try/catch包裹fetch，对401自动跳登录页，对5xx显示降级提示，对网络超时做指数退避重试——最多重试3次，间隔1秒、2秒、4秒。实际在电商项目里，有个场景是订单提交时需要先调库存校验接口、再调支付接口、最后更新订单状态，三个接口有依赖关系。用async/await串起来代码很清晰，不用像回调那样一层层嵌套。Promise.all我会用在无依赖的并行请求上，比如首页同时请求用户信息、未读消息、待办事项，能节省60%的等待时间。错误处理上我习惯在捕获到异常后先log到控制台，再根据错误类型给用户不同的提示，而不是弹一个'网络错误'了事。",

    # 第7题：故障排查（230字）
    "博客上线后遇到一个诡异问题：每隔几小时页面就变白屏，刷新又好了。一开始以为是内存泄漏，用Chrome Memory面板拍了快照对比，没发现异常增长。然后用Performance面板录了一段操作过程，发现每次从文章页返回列表页时，JS执行时间突然从正常的30毫秒飙升到800多毫秒。顺藤摸瓜发现是Vue Router的keep-alive缓存了太多页面组件，每个组件里又订阅了全局事件总线，事件处理器越积越多。解决方案：给keep-alive加了max=5限制，同时修改了事件监听方式，在组件deactivated时removeEventListener，activated时再addEventListener。修复后白屏问题彻底消失。另一个优化是打包体积——引入webpack-bundle-analyzer后发现ant-design被全量引入，改成按需加载后bundle从1.2MB降到380KB，这是性价比最高的优化。",

    # 第8题：团队协作（260字）
    "实习时最典型的冲突是和后端关于接口设计的分歧。我做CMS的富文本编辑器，需要后端提供一个文件上传接口。后端同事给的是multipart/form-data，一次只能传一个文件，返回格式是包装了好几层嵌套的对象。我提出改成支持批量上传，返回扁平结构。他觉得现有实现够用，改接口有风险。我没有直接硬刚，而是先私下和他聊了聊他的顾虑——原来他担心改接口会影响其他已经在用的模块。然后我写了份文档，列举了三个case：编辑一篇带10张图的文章，用现有接口要调11次（1次保存+10次上传），改成批量只需要2次，还画了时序图对比。同时保证我会做好前端的兼容处理，旧接口不会受影响。他看完后觉得有道理，花半天改了接口，我们联调一次通过。这事让我学到：技术分歧不可怕，关键是替对方考虑他的风险点，用数据说话而不是拍桌子。"
]


print("=" * 70)
print("                 AI 面试陪练 - 完整流程测试")
print("=" * 70)
print()
print(f"简历: 张三，计算机本科，React/TypeScript/Node.js/Docker")
print(f"      3个项目 + 1段实习，全部有量化数据")
print(f"目标: 前端开发工程师")
print()

print("=" * 70)
print("阶段一：启动面试")
print("=" * 70)
result = start_interview(resume, "前端开发工程师")
session_id = result["session_id"]
print(f"  会话ID: {session_id}")
print(f"  工具调用: {result['tools_used']}")
print(f"  生成题目数: {result['total_questions']}")
print(f"  首题: {result['question']}")
print()

for i, ans in enumerate(answers):
    print("=" * 70)
    print(f"  第 {i+1} / 8 题")
    print("=" * 70)
    
    print(f"\n  【用户回答】({len(ans)}字)")
    # 分行显示回答，每行缩进
    for line in ans.split('\n'):
        print(f"  {line}")
    print()
    
    r1 = evaluate_answer(session_id, ans)
    
    if r1.get("is_followup"):
        print(f"  [追问] 系统判定需要追问")
        print(f"  [追问内容] {r1['followup_question']}")
        
        followup_ans = f"{ans} 补充回答：针对您追问的点，我在实际项目中确实应用了对应的技术方案，有明确的量化数据和成果。如果需要，我可以进一步展开具体的实现细节和决策过程。"
        
        print(f"\n  [用户补充回答] ({len(followup_ans)}字)")
        print(f"  {followup_ans[:200]}...")
        print()
        
        r2 = evaluate_answer(session_id, followup_ans)
        final_score = r2
        print(f"  [追问后评分] {final_score.get('score')} 分")
    else:
        final_score = r1
        print(f"  [直接评分] {final_score.get('score')} 分")
    
    # 显示维度评分
    if final_score.get('dimension_scores'):
        d = final_score['dimension_scores']
        print(f"  +---------------------------------------+")
        print(f"  | 内容相关性(25):  {d.get('content_relevance', '?'):>3}                  |")
        print(f"  | 专业知识  (25):  {d.get('professional_accuracy', '?'):>3}                  |")
        print(f"  | 表达清晰度(20):  {d.get('clarity', '?'):>3}                  |")
        print(f"  | STAR完整性(20):  {d.get('star_completeness', '?'):>3}                  |")
        print(f"  | 岗位匹配度(10):  {d.get('position_match', '?'):>3}                  |")
        print(f"  | 总分(100):       {d.get('total', '?'):>3}                  |")
        print(f"  +---------------------------------------+")
    
    if final_score.get('feedback'):
        print(f"  [评语] {final_score['feedback'][:150]}")
    
    if final_score.get('next_question'):
        print(f"\n  -> 进入下一题")
        print(f"  [下一题] {final_score['next_question'][:100]}")
    else:
        print(f"\n  [面试结束] 8题全部完成!")
    print()

print()
print("=" * 70)
print("阶段二：结束面试 - 生成完整报告")
print("=" * 70)
report = finish_interview(session_id)
print(f"""
  综合总分: {report['overall_score']} / 100
  完成题数: {report['total_questions_answered']}

  维度平均分:
    内容相关性: {report['dimension_averages'].get('content_relevance', '?')} / 25
    专业知识:   {report['dimension_averages'].get('professional_accuracy', '?')} / 25
    表达清晰度: {report['dimension_averages'].get('clarity', '?')} / 20
    STAR完整性: {report['dimension_averages'].get('star_completeness', '?')} / 20
    岗位匹配度: {report['dimension_averages'].get('position_match', '?')} / 10

  {report['summary']}
""")

print(f"  ── STAR 改写建议（{len(report['star_suggestions'])}条低分题）──")
for idx, s in enumerate(report['star_suggestions'], 1):
    print(f"\n  改写 {idx}: {s['question'][:60]}...")
    # 截取前200字显示
    star_text = s['star_rewrite']
    for line in star_text.split('\n')[:8]:
        print(f"  {line[:120]}")

print(f"\n  ── 练习计划 ──")
print(f"  {report['practice_plan'][:300]}")

print(f"\n{'=' * 70}")
print(f"                    全部测试通过!")
print(f"{'=' * 70}")
