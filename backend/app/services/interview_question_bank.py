import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

DEFAULT_POSITIONS = ["前端", "后端", "产品", "运营", "算法", "数媒"]
POSITION_KEYWORDS = {
    "前端": ["前端", "frontend", "fe", "web", "h5"],
    "后端": ["后端", "back-end", "backend", "be", "服务端", "服务器"],
    "产品": ["产品", "pm", "product"],
    "运营": ["运营", "operation", "ops", "growth"],
    "算法": ["算法", "algorithm", "ai", "机器学习", "深度学习", "nlp", "cv", "推荐"],
    "数媒": ["数媒", "数字媒体", "新媒体", "影视", "交互", "游戏", "动画", "设计"],
}

_QUESTION_BANK: Optional[List[Dict[str, Any]]] = None
_POSITION_QUESTIONS: Dict[str, List[Dict[str, str]]] = {}
_QUESTION_BANK_PATH = Path(__file__).resolve().parents[3] / "data" / "interview_question_bank.json"
_AUDIT_QUESTION_BANK_PATH = (
    Path(__file__).resolve().parents[3] / "data" / "audit_samples" / "interview_questions.jsonl"
)


def _dedupe_questions(questions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen: set = set()
    result: List[Dict[str, Any]] = []
    for question in questions:
        key = question.get("id") or question.get("question")
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(question)
    return result


def _dedupe_position_questions(items: List[Dict[str, str]]) -> List[Dict[str, str]]:
    seen: set = set()
    result: List[Dict[str, str]] = []
    for item in items:
        question = item.get("question")
        if not question or question in seen:
            continue
        seen.add(question)
        result.append(item)
    return result


def _map_audit_category_to_mode(category: str, difficulty: str) -> str:
    if "场景" in category or difficulty == "较难":
        return "压力面"
    return "技术面"


def _load_audit_questions() -> List[Dict[str, Any]]:
    if not _AUDIT_QUESTION_BANK_PATH.exists():
        return []

    questions: List[Dict[str, Any]] = []
    for line in _AUDIT_QUESTION_BANK_PATH.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        position = normalize_position(item.get("role", ""))
        if not position:
            continue
        expected_points = item.get("expected_points") or []
        mode = _map_audit_category_to_mode(
            str(item.get("category") or ""),
            str(item.get("difficulty") or ""),
        )
        questions.append(
            {
                "id": item.get("question_id"),
                "mode": mode,
                "category": item.get("category"),
                "positions": [position],
                "question": item.get("question"),
                "difficulty": item.get("difficulty"),
                "expected_focus": "；".join(expected_points),
                "follow_up": item.get("follow_up"),
                "scoring_tags": item.get("scoring_tags", []),
                "source": "audit_samples",
            }
        )
    return questions


def load_question_bank() -> List[Dict[str, Any]]:
    global _QUESTION_BANK, _POSITION_QUESTIONS
    if _QUESTION_BANK is not None:
        return _QUESTION_BANK
    try:
        content = _QUESTION_BANK_PATH.read_text(encoding="utf-8")
        data = json.loads(content)
        base_questions = data.get("questions", [])
        audit_questions = _load_audit_questions()
        _QUESTION_BANK = _dedupe_questions(base_questions + audit_questions)
        _POSITION_QUESTIONS.clear()
        _POSITION_QUESTIONS.update(data.get("position_banks", {}) or {})
        for question in audit_questions:
            question_text = question.get("question")
            if not question_text:
                continue
            for position in question.get("positions", []):
                _POSITION_QUESTIONS.setdefault(position, []).append(
                    {
                        "mode": question.get("mode", "技术面"),
                        "question": question_text,
                        "source": "audit_samples",
                    }
                )
        for position, items in list(_POSITION_QUESTIONS.items()):
            _POSITION_QUESTIONS[position] = _dedupe_position_questions(items)
        logger.info(
            "Loaded %d questions and %d position banks from question bank",
            len(_QUESTION_BANK),
            len(_POSITION_QUESTIONS),
        )
    except Exception as exc:
        logger.warning("Failed to load question bank: %s", exc)
        _QUESTION_BANK = []
        _POSITION_QUESTIONS.clear()
    return _QUESTION_BANK


def normalize_position(target_position: str) -> str:
    if not target_position:
        return ""
    lowered = target_position.lower()
    for standard, aliases in POSITION_KEYWORDS.items():
        for alias in aliases:
            if alias.lower() in lowered:
                return standard
    return ""


def get_question_bank_summary() -> Dict[str, Any]:
    questions = load_question_bank()
    if not questions:
        return {
            "total": 0,
            "modes": {},
            "difficulties": {},
            "categories": [],
            "positions": {},
            "position_bank_count": 0,
        }
    modes: Dict[str, int] = {}
    difficulties: Dict[str, int] = {}
    categories: set = set()
    positions: Dict[str, int] = {pos: 0 for pos in DEFAULT_POSITIONS}
    for question in questions:
        mode = question.get("mode", "未知")
        modes[mode] = modes.get(mode, 0) + 1
        difficulty = question.get("difficulty", "unknown")
        difficulties[difficulty] = difficulties.get(difficulty, 0) + 1
        category = question.get("category")
        if category:
            categories.add(category)
        for position in question.get("positions", []):
            if position in positions:
                positions[position] += 1
    return {
        "total": len(questions),
        "modes": modes,
        "difficulties": difficulties,
        "categories": sorted(categories),
        "positions": positions,
        "position_bank_count": len(_POSITION_QUESTIONS),
    }


def get_position_question_pool(position: str, interview_mode: str) -> List[str]:
    load_question_bank()
    normalized = normalize_position(position)
    if not normalized or normalized not in _POSITION_QUESTIONS:
        return []

    mode_pool = [
        item["question"]
        for item in _POSITION_QUESTIONS[normalized]
        if item.get("mode") == interview_mode and item.get("question")
    ]
    if mode_pool:
        return mode_pool

    return [
        item["question"]
        for item in _POSITION_QUESTIONS[normalized]
        if item.get("question")
    ]
