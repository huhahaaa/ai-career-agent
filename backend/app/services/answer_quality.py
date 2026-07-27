"""Answer Quality Agent —— 面试回答质量检定。

集中检定候选人的回答是否：乱码 / 脏话（二者归为“非作答”一类）、与题目相关、
回答合理/连贯。并给出噪声占比，用于“容忍正常人回答中少量输入错误”。

双轨设计：
- 规则轨道始终运行（mock 模式也完整可用，零额外成本）。
- LLM 轨道在 settings.llm_provider 可用时启用，用语义判断相关性/合理性，
  作为规则结果的增强；调用失败自动回退到规则轨道。

容错原则（区分“正常人输入习惯”和“真乱码”）：
- 纯数字（3年/40%）、常见缩写（AI/ML/B2B）、语气词重复（哈哈哈）、
  标点重复（。。。/！！！）、网络口头语（666）都不判乱码。
- 弱灌水词（“废话”“随便写写”）只在短文本中触发，长回答里的正常用法
  （如“不说废话，直接讲成果”）不误伤。
- 只有噪声占主导（重复垃圾占比 >=40%、键盘沙拉 >=2 处、随机字母长串）才判乱码。
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, Iterator, List, Optional, Tuple

from app.core.config import settings

logger = logging.getLogger(__name__)


# ── 脏话 / 非作答词表 ────────────────────────────────────────────────────
# 强脏话：任何长度文本中命中即判非作答（子串匹配，均为无歧义词）。
_ABUSE_STRONG = [
    "草泥马", "尼玛", "他妈的", "妈的", "傻逼", "傻比", "傻b", "傻B",
    "去死", "滚蛋", "fuck", "shit",
]
# 短拉丁骂词：必须词边界匹配（避免 B2B 命中 2b、absent 命中 sb）。
_ABUSE_SHORT_LATIN = ["sb", "2b", "asdf", "nmsl"]
# 弱灌水词：只在短文本（<15 字）触发——长回答里可能是正常用法（“不说废话”）。
_FILLER_TOKENS = ["废话", "废物", "随便写写", "测试测试", "不知道写什么"]

# 技术关键词（命中即视为“有效内容”，避免把含技术词的真实回答误判为乱码）
TECH_KEYWORDS_LOWER = [
    "react", "vue", "angular", "node", "python", "java", "go", "rust",
    "typescript", "javascript", "sql", "sqlalchemy", "sqlite", "mysql",
    "mongodb", "redis", "docker", "kubernetes", "k8s", "aws", "git",
    "linux", "http", "api", "rest", "css", "html", "spring", "django",
    "flask", "fastapi", "uvicorn", "pydantic", "chroma", "openai", "llm",
    "机器学习", "深度学习", "数据", "算法", "模型", "训练", "优化", "性能",
    "部署", "测试", "架构", "设计模式", "敏捷",
    "缓存", "接口", "微服务", "重构", "服务", "高并发", "稳定性", "分布式",
]

# 常见 1~3 字符缩写/口语拉丁词，不算键盘沙拉（正常人回答高频出现）。
_COMMON_SHORT_LATIN = {
    "ai", "ml", "ui", "ux", "qa", "pm", "hr", "it", "ci", "cd", "db",
    "os", "ip", "id", "ok", "app", "web", "bug", "api", "sdk", "llm",
    "gpu", "cpu", "b2b", "b2c", "c2c", "o2o", "kpi", "okr", "3d", "2d",
    "vs", "er", "orm", "jwt", "tcp", "udp", "dns", "cdn", "css", "xml",
    "gpt", "rag", "etl", "crm", "erp", "iot", "star",
}

# 语气/拟声字：其重复（哈哈哈、嗯嗯嗯）是正常表达，不算灌水重复。
_INTERJECTION_CHARS = set("哈呵嘿嗯哦噢喔呀啊哎唉嘛咯啦呗哇")

# 连接词 / 结构标记，用于合理性判定
_STRUCTURE_MARKERS = [
    "因为", "所以", "通过", "负责", "使用", "实现", "参与", "完成", "主导",
    "首先", "其次", "最后", "例如", "比如", "我们", "项目", "经验", "成果",
]

_STOPWORDS = set(
    "的了在是与和及对等为被把让给到也都很再都一个这那我们你们他们它其"
    "且并或因为所以通过如何什么怎么哪些是否能否为什么该这个那个"
)

_VOWELS = set("aeiou")

# QWERTY 键盘三行，用于识别“键盘行乱码”（asd/qwe/zxc 等全在同一行的随机敲键）。
_KEYBOARD_ROWS = ["qwertyuiop", "asdfghjkl", "zxcvbnm"]


def _same_keyboard_row(chars: str) -> bool:
    rows = {next((r for r in _KEYBOARD_ROWS if c in r), None) for c in chars}
    return len(rows) == 1 and None not in rows


@dataclass
class AnswerVerdict:
    """对一条回答的检定结论。"""

    valid: bool
    category: str  # valid | invalid_nonanswer | off_topic | low_quality
    gibberish: bool
    abuse: bool
    relevance: float  # 0~1 与题目相关性
    coherence: float  # 0~1 合理性/连贯度
    noise_ratio: float  # 噪声字符占比（容错核心指标）
    signals: List[str] = field(default_factory=list)
    confidence: float = 0.0
    llm_used: bool = False


# ── 规则轨道 ────────────────────────────────────────────────────────────
def _rule_abuse(text: str) -> bool:
    low = text.lower()
    if any(tok.lower() in low for tok in _ABUSE_STRONG):
        return True
    # 短拉丁骂词：词边界匹配，B2B/absent 等不误伤。
    for tok in _ABUSE_SHORT_LATIN:
        if re.search(rf"(?<![a-z0-9]){re.escape(tok)}(?![a-z0-9])", low):
            return True
    # 弱灌水词只在短文本触发（长回答里“不说废话”是正常用法）。
    if len(text) < 15 and any(tok in text for tok in _FILLER_TOKENS):
        return True
    return False


def _iter_latin_runs(text: str) -> Iterator[Tuple[int, int, str]]:
    """迭代文本中的连续拉丁字母/数字串，产出 (start, end_exclusive, run_text)。"""
    for m in re.finditer(r"[A-Za-z0-9]+", text):
        yield m.start(), m.end(), m.group(0)


def _is_salad_run(text: str, start: int, end: int, run_text: str) -> bool:
    """判断一个短拉丁串是否为“键盘沙拉”（被中文夹着的随机敲键）。

    纯数字（3年/40%）、常见缩写（AI/B2B）、技术词一律不算。
    """
    low = run_text.lower()
    if run_text.isdigit():
        return False
    if len(low) > 3:
        return False
    if low in _COMMON_SHORT_LATIN or low in TECH_KEYWORDS_LOWER:
        return False
    text_has_cjk = any("\u4e00" <= c <= "\u9fff" for c in text)
    if len(low) == 3:
        # 3 字母键盘行（asd/qwe/zxc）：中文作答里出现即视为沙拉，与是否紧贴中文无关。
        return _same_keyboard_row(low) and text_has_cjk
    # 1~2 字母：需紧贴中文（避免误伤代码里的 i/in 等孤立拉丁）。
    left_cjk = start > 0 and "\u4e00" <= text[start - 1] <= "\u9fff"
    right_cjk = end < len(text) and "\u4e00" <= text[end] <= "\u9fff"
    return left_cjk or right_cjk


def _is_random_latin_run(run_text: str) -> bool:
    """检测长随机字母串（如 DAFGasdhfkjahs / qwerty / asdfgh）：

    - 辅音连击 5+ 或元音占比 < 0.2（>=7 字母）；
    - 5+ 字母的纯键盘行（qwerty/asdfgh/zxcvbn）视为随机敲键。
    已知技术词（含子串，如 sqlalchemy 含 sql）不判随机。
    """
    low = run_text.lower()
    if not low.isalpha():
        return False
    if any(kw in low for kw in TECH_KEYWORDS_LOWER if len(kw) >= 3):
        return False
    vowel_ratio = sum(1 for c in low if c in _VOWELS) / len(low)
    if len(low) >= 5 and _same_keyboard_row(low) and vowel_ratio < 0.3:
        return True
    if len(low) < 7:
        return False
    max_consonant_streak = max(
        (len(s) for s in re.split(r"[aeiouy]", low)), default=0
    )
    return max_consonant_streak >= 5 or vowel_ratio < 0.2


def _repeat_noise_spans(text: str) -> int:
    """统计“真灌水型”连续重复片段的总字符数。

    排除正常输入习惯：语气词重复（哈哈哈/嗯嗯嗯）、标点重复（。。。/！！！）、
    纯数字重复（666/888）。只统计实义内容的连续重复（祈福祈福祈福/发发发发）。
    """
    total = 0
    for m in re.finditer(r"(.{1,4})\1{2,}", text):
        unit = m.group(1)
        if all(c in _INTERJECTION_CHARS for c in unit):
            continue
        if not re.search(r"[\u4e00-\u9fffA-Za-z]", unit):
            continue  # 纯标点/空白/数字重复：正常输入习惯
        if unit.isdigit() or unit.isspace():
            continue
        total += len(m.group(0))
    return total


def _rule_gibberish(text: str) -> Tuple[bool, float, List[str]]:
    """规则兜底用的“乱码”判定（仅当 LLM 未启用或失败时调用）。

    设计原则：规则只兜底“明显无意义”的内容，不做精细语义判断（语义交给 LLM）。
    因此键盘行/随机字母串只有在“几乎占据整段、缺乏真实中文语义”时才算噪声——
    避免把“回答里举例提到 asd/qwe/zxc”“含真实中文句子的英文/代码作答”误判为乱码。
    """
    signals: List[str] = []
    n = len(text)
    if n == 0:
        return True, 1.0, ["空回答"]

    cjk_chars = sum(1 for c in text if "\u4e00" <= c <= "\u9fff")
    latin_runs = list(_iter_latin_runs(text))
    salad_chars = 0
    random_chars = 0
    for start, end, run in latin_runs:
        if _is_salad_run(text, start, end, run):
            salad_chars += len(run)
        elif _is_random_latin_run(run):
            random_chars += len(run)

    # 有效中文句子里夹带键盘行示例：不判乱码（容忍少量键盘串输入）。
    # 仅当“几乎无中文语义（中文极少）+ 噪声占拉丁主体”才记为乱码。
    if cjk_chars < 3:
        if salad_chars >= 6:
            signals.append("键盘随机输入（沙拉特征）")
        if random_chars >= 7:
            signals.append("随机字母长串")

    repeat_chars = _repeat_noise_spans(text)
    if repeat_chars / n >= 0.4:
        signals.append("连续重复灌水")

    noise = min(n, salad_chars + random_chars + repeat_chars)
    noise_ratio = round(noise / n, 3)
    # 综合噪声占比兜底：过半内容是噪声且中文极少，即便单项未达标也判乱码。
    if not signals and noise_ratio >= 0.5 and n >= 10 and cjk_chars < 3:
        signals.append("有效内容占比过低")

    return bool(signals), noise_ratio, signals


def _meaningful_chars(text: str) -> set:
    """抽取非停用字的中文字符集合，用于字符级相关性兜底。"""
    return {
        ch for ch in text
        if "\u4e00" <= ch <= "\u9fff" and ch not in _STOPWORDS
    }


def _latin_ratio(text: str) -> float:
    """文本中拉丁字母占所有字母数字字符的比例（识别英文/代码作答）。"""
    alnum = [c for c in text if c.isalnum()]
    if not alnum:
        return 0.0
    lat = sum(1 for c in alnum if c.isascii() and c.isalpha())
    return lat / len(alnum)


def _rule_coherence(text: str) -> float:
    low = text.lower()
    tech_hits = sum(1 for k in TECH_KEYWORDS_LOWER if k in low)
    tech_factor = min(tech_hits, 3) / 3.0
    has_structure = any(m in text for m in _STRUCTURE_MARKERS)

    # 英文 / 代码作答：中文结构标记不适用，改用词数与句子特征估连贯度。
    if _latin_ratio(text) > 0.6:
        words = re.findall(r"[A-Za-z]+", text)
        has_sent = any(p in text for p in (".", "?", "!", ";", "{"))
        coh = 0.4 + 0.3 * min(len(words), 40) / 40.0 + (0.2 if has_sent else 0.0) \
            + 0.1 * tech_factor
        return round(min(1.0, coh), 3)

    length_factor = 0.3 if len(text) >= 50 else 0.15
    coherence = 0.4 * tech_factor + (0.3 if has_structure else 0.0) + length_factor
    return round(min(1.0, coherence), 3)


def _extract_tokens(text: str) -> set:
    """抽取中文 2~3 字连续片段（剔除以停用字开头/结尾的噪声），作为主题词集合。"""
    tokens: set = set()
    for m in re.finditer(r"[\u4e00-\u9fff]{2,}", text):
        seg = m.group(0)
        for size in (2, 3):
            for s in range(len(seg) - size + 1):
                tok = seg[s:s + size]
                if tok[0] in _STOPWORDS or tok[-1] in _STOPWORDS:
                    continue
                tokens.add(tok)
    return tokens


def _rule_relevance(question: str, answer: str, job_requirements: str = "") -> float:
    """规则相关性：主题词重叠 + 单字重叠 + 技术词重叠，叠加 mock 软兜底。

    - 仅用 2~3 字主题词重叠会把同义改写（如“项目经历”vs“主导了电商项目”）
      误判为跑题，故叠加单字重叠。
    - 连贯且含结构/技术、并与题目有少量词汇交集的回答，在 mock（无语义判断）
      下默认视为切题，避免把正常作答误标 off_topic；真正跑题的短回答仍会因
      相关性极低且无结构被识别。
    """
    q_tokens = _extract_tokens(question)
    a_tokens = _extract_tokens(answer)
    tok_rel = (len(q_tokens & a_tokens) / len(q_tokens)) if q_tokens else 0.0

    q_chars = _meaningful_chars(question)
    a_chars = _meaningful_chars(answer)
    char_rel = (len(q_chars & a_chars) / len(q_chars)) if q_chars else 0.0

    q_tech = {k for k in TECH_KEYWORDS_LOWER if k in question.lower()}
    j_tech = {k for k in TECH_KEYWORDS_LOWER if k in (job_requirements or "").lower()}
    a_tech = {k for k in TECH_KEYWORDS_LOWER if k in answer.lower()}
    base_tech = q_tech | j_tech
    tech_rel = (len(base_tech & a_tech) / len(base_tech)) if base_tech else 0.0

    rel = max(tok_rel, 0.6 * char_rel, 0.7 * tech_rel)

    # 软兜底：连贯 + 与题目有词汇交集或含技术词 → 视为切题（mock 无语义判断）。
    coh = _rule_coherence(answer)
    if coh >= 0.4 and (char_rel > 0.05 or len(a_tech) >= 1):
        rel = max(rel, 0.5)

    # 英文问答：题目与回答均为英文，直接给合理相关度（mock 无法做语义判断）。
    if _latin_ratio(question) > 0.6 and _latin_ratio(answer) > 0.6:
        rel = max(rel, 0.6)

    return round(min(1.0, rel), 3)


def _extract_json(text: str) -> Dict[str, Any]:
    """从 LLM 输出中稳健提取 JSON 对象（容忍 markdown 围栏与前后多余文字）。

    LLM 偶尔会输出 ```json ...``` 或在 JSON 前后加解释文字，直接 json.loads 会失败、
    进而回退规则轨道导致判定不稳定。这里先剥离围栏，再截取首个 {...} 解析。
    """
    if not text:
        return {}
    cleaned = re.sub(r"```(?:json)?\s*([\s\S]*?)```", r"\1", text).strip()
    try:
        obj = json.loads(cleaned)
        return obj if isinstance(obj, dict) else {}
    except (TypeError, json.JSONDecodeError):
        pass
    match = re.search(r"\{[\s\S]*\}", cleaned)
    if match:
        try:
            obj = json.loads(match.group(0))
            return obj if isinstance(obj, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


# ── LLM 轨道 ────────────────────────────────────────────────────────────
_client: Any = None


def _llm_enabled() -> bool:
    return (
        settings.llm_provider.lower() not in {"", "mock", "none", "local"}
        and bool(settings.llm_api_key)
    )


def _get_client() -> Any:
    global _client
    if _client is None:
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError("openai package is not installed") from exc
        _client = OpenAI(
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
            timeout=30.0,
        )
    return _client


def _llm_judge(
    question: str,
    answer: str,
    target_position: str,
    job_requirements: str,
    interview_mode: str,
) -> Tuple[float, float, List[str]]:
    """用语义判断相关性/合理性。失败抛异常，由调用方回退到规则轨道。"""
    prompt = f"""你是面试回答质量检定器。只输出 JSON，不要其他内容。

面试模式：{interview_mode}
目标岗位：{target_position}
面试问题：{question}
岗位要求：{job_requirements}
候选人回答：{answer}

请判断：
1. relevance：回答与问题的相关性（0~1，完全跑题为 0，精准切题为 1）
2. coherence：回答的合理性/连贯度（0~1，纯水词或无逻辑为 0，结构清晰有实质为 1）
3. is_off_topic：是否明显跑题（true/false）
4. signals：命中的质量信号（1~3 个中文短词，如“技术细节充分”“缺乏量化”“偏题”）

严格输出 JSON：
{{"relevance": 数字, "coherence": 数字, "is_off_topic": true/false, "signals": ["...", "..."]}}"""
    client = _get_client()
    resp = client.chat.completions.create(
        model=settings.llm_model,
        messages=[
            {"role": "system", "content": "你是严格的回答质量检定器，只输出 JSON。"},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
        max_tokens=400,
    )
    raw = resp.choices[0].message.content or ""
    parsed = _extract_json(raw)
    return (
        float(parsed.get("relevance", 0.0)),
        float(parsed.get("coherence", 0.0)),
        list(parsed.get("signals", [])),
    )


def _llm_classify(
    question: str,
    answer: str,
    target_position: str,
    job_requirements: str,
    interview_mode: str,
) -> Dict[str, Any]:
    """让 LLM 直接给出“乱码 / 脏话 / 跑题 / 灌水”等语义判定，并容忍正常人少量输入错误。

    设计原则（按用户要求不再写死规则）：
    - 相关性、合理性、是否乱码、是否脏话、是否跑题，全部交给 LLM 语义判断；
    - 规则只做最基础的兜底（空/极短），不抢判；
    - 关键在于“容忍”：候选人回答里若出现键盘行示例（如 asd/qwe/zxc）、少量错字、
      语气词、个别无意义片段，只要整体是真实作答，就不应判乱码/非作答。

    失败抛异常，由调用方回退到规则轨道。
    """
    prompt = f"""你是面试回答质量检定器。请只输出 JSON，不要其他内容。

目标岗位：{target_position}
面试问题：{question}
岗位要求：{job_requirements}
面试模式：{interview_mode}
候选人回答：{answer}

请综合判断这份回答的质量，并严格输出 JSON：
{{
  "gibberish": true/false,   # 是否整体为无意义乱码/随机敲键。判定看【语义实质】而非是否出现键盘串：
                             #   - 仅当回答主体由连续键盘行（asdfghjkl / qwertyuiop / zxcvbnm 等整行敲键）或随机字母/字符长串构成、缺乏真实语义内容时，才判 true；
                             #   - 若回答整体讲述了真实经历/技术/成果/角色（即便举例用到 asd/qwe/zxc，或含少量错字、语气词、表情符号），一律判 false；
                             #   - 若回答中夹杂一大段纯键盘沙拉（连续多行 qwerty/asdf/zxcv）且缺乏真实内容，也应判 true。
  "abuse": true/false,       # 是否含辱骂/脏话/纯粹非作答（如只写“随便写写”“不知道”且无任何实质）
  "off_topic": true/false,   # 是否明显跑题、完全没有回应题目
  "relevance": 0~1,          # 与题目的相关性
  "coherence": 0~1,          # 连贯度/合理性（容忍少量错字、语气词、个别无意义片段）
  "signals": ["..."]         # 1~3 个中文质量信号，如“技术细节充分”“缺乏量化”“偏题”“含不当内容”
}}

重要：正常人的回答常有少量错别字、口语重复、表情符号或单个无意义片段，只要整体是真实作答就把 gibberish/abuse 判为 false。
特例：若回答包含真实中文语义词（项目/方案/负责/稳定/经验/成果/接口 等），其中的 asd/qwe/zxc 等只是举例或占位符，
     整体仍视为真实作答，gibberish=false、valid=true，不要因出现键盘行就判乱码。"""
    client = _get_client()
    resp = client.chat.completions.create(
        model=settings.llm_model,
        messages=[
            {"role": "system", "content": "你是严格的回答质量检定器，只输出 JSON。"},
            {"role": "user", "content": prompt},
        ],
        temperature=0.0,
        seed=42,
        max_tokens=500,
    )
    raw = resp.choices[0].message.content or ""
    parsed = _extract_json(raw)
    return {
        "gibberish": bool(parsed.get("gibberish", False)),
        "abuse": bool(parsed.get("abuse", False)),
        "off_topic": bool(parsed.get("off_topic", False)),
        "relevance": float(parsed.get("relevance", 0.0)),
        "coherence": float(parsed.get("coherence", 0.0)),
        "signals": list(parsed.get("signals", [])),
    }


# ── Agent 入口 ───────────────────────────────────────────────────────────
class AnswerQualityAgent:
    """回答质量检定 Agent（规则 + LLM 双轨）。"""

    @staticmethod
    def judge(
        question: str,
        answer: str,
        target_position: str = "",
        job_requirements: str = "",
        interview_mode: str = "",
    ) -> AnswerVerdict:
        stripped = (answer or "").strip()

        # 基础兜底：空 / 极短（<2 字）一律非作答。其余判定全部交给 LLM，
        # 不再用写死的键盘行/重复/灌水规则抢判，以避免把正常作答误伤为乱码。
        if len(stripped) < 2:
            return AnswerVerdict(
                valid=False, category="invalid_nonanswer", gibberish=True, abuse=False,
                relevance=0.0, coherence=0.0, noise_ratio=1.0,
                signals=["回答过短/空"], confidence=0.95,
            )

        # LLM 主判：乱码 / 脏话 / 跑题 / 相关性 / 合理性 + 容忍少量输入错误。
        if _llm_enabled():
            try:
                c = _llm_classify(
                    question, stripped, target_position, job_requirements, interview_mode
                )
                gibberish = bool(c.get("gibberish"))
                abuse = bool(c.get("abuse"))
                off_topic = bool(c.get("off_topic"))
                relevance = float(c.get("relevance", 0.0))
                coherence = float(c.get("coherence", 0.0))
                signals = list(c.get("signals", []))
                if gibberish:
                    signals.append("疑似乱码")
                if abuse:
                    signals.append("含不当/灌水内容")
                if off_topic:
                    signals.append("偏题")
                category = "valid"
                if gibberish or abuse:
                    category = "invalid_nonanswer"
                elif off_topic:
                    category = "off_topic"
                elif coherence < 0.35 or relevance < 0.35:
                    category = "low_quality"
                return AnswerVerdict(
                    valid=not (gibberish or abuse),
                    category=category, gibberish=gibberish, abuse=abuse,
                    relevance=relevance, coherence=coherence, noise_ratio=0.0,
                    signals=signals, confidence=0.9, llm_used=True,
                )
            except Exception as exc:  # LLM 失败 → 回退规则轨道
                logger.warning("LLM classify failed, fallback to rules: %s", exc)

        # ── 规则兜底（仅当 LLM 未启用或调用失败）─────────────────────────
        abuse = _rule_abuse(stripped)
        gibberish, noise_ratio, g_signals = _rule_gibberish(stripped)
        signals = list(g_signals)
        if abuse:
            signals.append("含不当/灌水内容")
        if gibberish or abuse:
            return AnswerVerdict(
                valid=False, category="invalid_nonanswer", gibberish=gibberish, abuse=abuse,
                relevance=0.0, coherence=0.0, noise_ratio=noise_ratio,
                signals=signals, confidence=0.95,
            )

        coherence = _rule_coherence(stripped)
        relevance = _rule_relevance(question, stripped, job_requirements)
        category = "valid"
        if relevance < 0.15 and coherence < 0.4:
            category = "off_topic"
        elif coherence < 0.35 or relevance < 0.35:
            category = "low_quality"
        return AnswerVerdict(
            valid=True, category=category, gibberish=False, abuse=False,
            relevance=relevance, coherence=coherence, noise_ratio=noise_ratio,
            signals=signals, confidence=0.85, llm_used=False,
        )


def judge_answer_quality(
    question: str,
    answer: str,
    target_position: str = "",
    job_requirements: str = "",
    interview_mode: str = "",
) -> AnswerVerdict:
    """模块级便捷入口。"""
    return AnswerQualityAgent.judge(
        question, answer, target_position, job_requirements, interview_mode
    )
