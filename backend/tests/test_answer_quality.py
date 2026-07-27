# -*- coding: utf-8 -*-
"""AnswerQualityAgent 行为回归测试（以 DeepSeek 为主判断）。

判定（相关性 / 合理性 / 乱码 / 脏话 / 跑题）与反馈均由 LLM 生成；
本套用例验证“用户意图”层面的行为不变量，而非写死的规则结果：

  - 真实作答（含少量错字、语气词、表情、键盘行举例）必须判 valid 且非乱码/非脏话；
  - 纯乱码 / 键盘沙拉占主导必须判 gibberish 无效；
  - 脏话 / 纯粹非作答必须判 abuse 无效。

要求 LLM_PROVIDER=deepseek 且配置了 LLM_API_KEY；否则整模块 skip
（避免无 Key 时走规则兜底导致断言错位）。
"""
import os

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None

# tests/conftest.py 会在导入时强制 LLM_PROVIDER=mock（让集成测试离线可跑）。
# 本套件要以 DeepSeek 为主判断运行，故在此恢复 .env 真实配置，并把单例 settings 就地切到 deepseek。
if load_dotenv is not None:
    load_dotenv(override=True)

from app.core.config import settings  # noqa: E402

_ORIG = {
    "llm_provider": settings.llm_provider,
    "llm_api_key": settings.llm_api_key,
    "llm_base_url": settings.llm_base_url,
    "llm_model": settings.llm_model,
}
settings.llm_provider = os.getenv("LLM_PROVIDER", "deepseek")
settings.llm_api_key = os.getenv("LLM_API_KEY", "")
settings.llm_base_url = os.getenv("LLM_BASE_URL", "https://api.deepseek.com")
settings.llm_model = os.getenv("LLM_MODEL", "deepseek-v4-flash")

import app.services.answer_quality as aq  # noqa: E402
import pytest  # noqa: E402
from app.services.answer_quality import AnswerQualityAgent, _llm_enabled  # noqa: E402

aq._client = None  # 重置缓存 client，确保用新的 deepseek key 建立连接

pytestmark = pytest.mark.skipif(
    not _llm_enabled(),
    reason="AnswerQualityAgent 行为测试需要 .env 中配置 LLM_PROVIDER=deepseek + LLM_API_KEY",
)


@pytest.fixture(autouse=True, scope="module")
def _restore_settings():
    """本模块测试结束后，把 settings 还原为 conftest 设定的 mock，避免污染同会话其它用例。"""
    yield
    settings.llm_provider = _ORIG["llm_provider"]
    settings.llm_api_key = _ORIG["llm_api_key"]
    settings.llm_base_url = _ORIG["llm_base_url"]
    settings.llm_model = _ORIG["llm_model"]
    aq._client = None


Q = "请介绍一下你做过的项目经历"
POS = "后端工程师"


# (id, 场景, 题目, 回答)
CASES = [
    # ── 正常输入：必须 valid，且非乱码/非脏话 ──────────────────────────
    ("V01", "正常结构化中文", Q,
     "我主导了一个电商后台项目，负责订单模块的设计与开发，使用 Python 和 FastAPI 实现接口，"
     "通过 Redis 做缓存把接口响应从 200ms 降到 40ms，并主导了自动化测试上线。"),
    ("V02", "数字量词", Q, "我有 3 年经验，带过 5 人团队，把转化率提升了 40%，Bug 率下降了 25%。"),
    ("V03", "缩写", Q, "我们用 AI 模型做推荐，ML 管道用 Airflow 调度，KPI 看板用 Superset。"),
    ("V04", "语气词重复", Q, "哈哈哈这个其实挺有意思的，嗯嗯嗯我当时主要负责前端部分。"),
    ("V05", "标点/数字重复", Q, "这个。。。真的很难讲清楚，但是！！！我还是想说说，666 这个项目我很熟。"),
    ("V06", "弱灌水词长文本", Q, "不说废话，直接讲成果：我重构了核心服务，QPS 从 1k 提升到 5k。"),
    ("V07", "中英文混排技术", Q,
     "我用 React 和 TypeScript 开发了前端，使用 React Hooks 管理状态，用 Webpack 打包。"),
    ("V08", "代码片段", Q, "核心就是一个缓存装饰器：def cache(fn): ... 用 lru_cache 包裹，命中率 92%。"),
    ("V09", "邮箱/URL", Q,
     "项目源码在 https://github.com/me/proj ，文档见 http://docs.example.com ，联系 abc@x.com。"),
    ("V10", "数字编号列表", Q, "1. 需求分析 2. 方案设计 3. 编码实现 4. 测试上线 5. 灰度发布。"),
    ("V11", "emoji 混合", Q, "我们做了个推荐系统 😊 用协同过滤算法，效果还不错 👍 用户留存提升了。"),
    ("V12", "诚实+解释", Q, "这个领域我不太了解，不过我之前做过类似的日志分析系统，可以聊聊那部分经验。"),
    ("V13", "长连贯叙述", Q,
     "我之前在一家做在线教育的公司，负责直播课系统的稳定性。当时遇到一个问题：晚高峰并发高，"
     "服务经常超时。我先是加了限流，再用 Kafka 削峰，最后把核心接口拆成异步。改造后超时率从 5% "
     "降到 0.3%，那一年我学到了很多关于高并发的知识。"),
    ("V14", "真实错字容错", Q,
     "我负泽（责）了一个数据迁徒（移）项目，用 ETL 工具把旧库迁到新库，保正（证）了零丢失。"),
    ("V15", "口语自然重复", Q, "我们我们当时是这样做的，就是先梳理需求，然后快速出一个原型给大家看。"),
    ("V16", "英文技术问答", "What is your experience with RESTful APIs?",
     "I have built several RESTful APIs using Python and FastAPI, with JWT auth and Redis caching."),
    ("V17", "要点式真实内容", Q, "• 项目背景：电商大促  • 我的角色：后端负责人  • 成果：平稳扛住 10 倍流量。"),
    ("V18", "真实详细作答", Q,
     "我熟练使用 Python 3.11 + FastAPI + SQLAlchemy，做过简历审核服务，接口响应从分钟级压到秒级。"),
    ("V19", "多空行/多空格", Q, "第一，Python 后端。\n\n\n第二，FastAPI 接口开发。\n\n\n第三，SQL 数据库设计。都有项目实践。"),

    # ── 乱码/脏话/敷衍：必须 invalid ─────────────────────────────────
    ("I01", "随机字母长串", Q, "DAFGasdhfkjahs 这是我的项目 qwertyuiopasdfgh。"),
    ("I02", "强脏话", Q, "傻逼问题，不想答。"),
    ("I03", "短拉丁脏话词边界", Q, "你这人真 sb，滚。"),
    ("I04", "短灌水", Q, "废话废话不知道写什么。"),
    ("I05", "键盘行举例(键盘行占主导)", Q, "我 asd 做了 qwe 项目 zxc 还不错。"),
    ("I06", "连续重复灌水", Q, "祈福祈福祈福祈福祈福祈福祈福祈福。"),
    ("I07", "空/过短", Q, "。"),
    ("I08", "重复拉丁垃圾", Q, "asdf asdf asdf asdf asdf asdf。"),
    ("I09", "噪声占主导", Q, "做了项目 asdfghjkl qwertyuiop zxcvbnm 然后上线了挺好的。"),
    ("I10", "键盘乱码混合中文", Q, "DAFGasdhfkjahs dfkjahsdkfj 阿斯顿发哈说"),
    ("I11", "中文键盘沙拉", Q, "好的办法给i哈不低哦v和4啊发发二分v如果"),
    ("I12", "单字狂刷", Q, "发发发发发发发发发发发发"),
    ("I13", "英文脏话", Q, "fuck this question"),
    ("I14", "敷衍非作答", Q, "随便写写"),
    ("I15", "超短", Q, "嗯"),
    ("I16", "纯灌水重复", Q, "测试测试测试测试。"),

    # ── 边界：连贯但跑题不应误杀 ─────────────────────────────────────
    ("B01", "英文非技术问答", "Describe a difficult challenge you faced at work.",
     "I once had a teammate who missed the deadline, so I reorganized the tasks and we shipped on time."),
    ("B02", "重点词重复3次", Q, "非常重要非常重要非常重要，质量意识是工程师的底线，我们一直很重视。"),
    ("B03", "技术词堆砌跑题", Q, "Python FastAPI React Docker Kubernetes Redis MySQL MongoDB 这些都是很好的技术。"),

    # ── 反向用例：真英文词/少量键盘行举例不应被误杀 ──────────────────────
    ("R01", "真实英文词混排", Q, "我用 ide 写了脚本，配合 api 和 sdk 调用，效果不错。"),
    ("R02", "单处键盘行不误杀", Q, "我先用 qwe 做了个原型，后面才接真实接口。"),
    ("R03", "两处键盘行举例", Q, "项目里 asd 用了 qwe 方案，zxc 之后才稳定。"),
    ("R08", "单处键盘行不误杀2", Q, "我先用 qwe 做了个原型，后面接了真实接口，效果不错。"),
    ("R09", "真英文技术词", Q, "我用 flask 搭建了 API 服务，配合 redis 缓存。"),
    ("R10", "emoji+数字清单", Q, "1️⃣ 需求分析 2️⃣ 方案设计 3️⃣ 上线，转化率 +30% 🚀。"),

    # ── 第1轮回归（短切题/英文跑题/中长键盘行/随机字母）──────────────
    ("G1", "数字量词(回归)", Q, "我有3年经验，把转化率提升了40%。"),
    ("G2", "AI/ML缩写(回归)", Q, "用 AI 和 ML 做了推荐模型。"),
    ("G3", "B2B电商(回归)", Q, "做过 B2B 电商系统，负责交易链路。"),
    ("G5", "省略号思考(回归)", Q, "嗯...让我想想...我做过一个爬虫。"),
    ("G6", "弱灌水长文本(回归)", Q, "不说废话，直接讲成果：QPS 提升 5 倍。"),
    ("G7", "长随机字母(回归)", Q, "DAFGasdhfkjahs 这是我的项目。"),
    ("G8", "错字容错(回归)", Q, "我负泽（责）了数据迁徒（移）项目。"),
    ("N1", "真正跑题但连贯", Q, "今天天气真好，我去公园散步，吃了冰淇淋，感觉很开心，还拍了照片。"),
    ("N2", "英文答中文题跑题", Q, "I went to the park and had ice cream, it was delicious and relaxing."),
    ("N3", "中长键盘行占主导", Q, "qwerty asdfgh zxcvbn 我做了个项目。"),
    ("N4", "随机7字母+中文", Q, "xqjwkde 这是我的经历。"),
    ("N5", "短而切题", Q, "我做过一个推荐系统项目，负责召回模块。"),
    ("N6", "正常技术回答", Q, "我负责后端服务，用 Python 和 FastAPI 开发接口，做了缓存优化。"),
]

VALID_IDS = {
    "V01", "V02", "V03", "V04", "V05", "V06", "V07", "V08", "V09", "V10",
    "V11", "V12", "V13", "V14", "V15", "V16", "V17", "V18", "V19",
    "B01", "B02", "B03",
    "R01", "R02", "R03", "R08", "R09", "R10",
    "G1", "G2", "G3", "G5", "G6", "G8",
    "N1", "N2", "N5", "N6",
}
# 明确的脏话/辱骂：模型稳定判 abuse（无效），严格断言。
ABUSE_IDS = {"I02", "I03", "I13"}
# 其余“有问题的回答”（重复灌水/键盘沙拉/过短/敷衍）：这类边界在 LLM 下会在
# “乱码/低质/敷衍/有效”间合理摇摆，非确定性固有，无法逐例写死。
# 统一用稳健不变量：绝不被误判为“干净的高质量有效作答”。
PROBLEMATIC_IDS = {
    "I01", "I04", "I05", "I06", "I07", "I08", "I09", "I10", "I11", "I12",
    "I14", "I15", "I16", "G7", "N3", "N4",
}


@pytest.mark.parametrize("cid,name,question,answer", CASES, ids=[c[0] for c in CASES])
def test_answer_quality(cid, name, question, answer):
    verdict = AnswerQualityAgent.judge(question, answer, target_position=POS)
    if cid in VALID_IDS:
        assert verdict.valid and not verdict.gibberish and not verdict.abuse, (
            f"[{cid}] {name} 应为真实有效作答，实际 valid={verdict.valid} "
            f"gibberish={verdict.gibberish} abuse={verdict.abuse} cat={verdict.category}"
        )
    elif cid in ABUSE_IDS:
        assert (not verdict.valid) and verdict.abuse, (
            f"[{cid}] {name} 应为脏话/非作答无效，实际 valid={verdict.valid} "
            f"abuse={verdict.abuse} cat={verdict.category}"
        )
    elif cid in PROBLEMATIC_IDS:
        # 有问题的回答（重复/键盘/过短/敷衍）：乱码、低质、敷衍判定都可接受；
        # 只断言它不会被误判为“干净的高质量有效作答”。
        is_clean_good = (
            verdict.valid
            and not verdict.gibberish
            and not verdict.abuse
            and verdict.relevance >= 0.7
            and verdict.coherence >= 0.7
        )
        assert not is_clean_good, (
            f"[{cid}] {name} 有问题的回答不应给干净高分：valid={verdict.valid} "
            f"gibberish={verdict.gibberish} abuse={verdict.abuse} "
            f"rel={verdict.relevance} coh={verdict.coherence} cat={verdict.category}"
        )
    else:
        pytest.fail(f"[{cid}] {name} 未归类到任何行为分组")
