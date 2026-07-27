from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field


class InterviewStartRequest(BaseModel):
    resume_text: str = ""
    resume_id: Optional[int] = None
    target_job_id: Optional[Union[int, str]] = None
    target_position: str = ""
    interview_mode: str = "技术面"


class InterviewQuestion(BaseModel):
    session_id: str
    interview_mode: str = "技术面"
    question: str
    tools_used: List[str] = []
    total_questions: int = 8
    position_bucket: str = ""


class InterviewAnswerRequest(BaseModel):
    answer: str = Field(..., min_length=1)
    question_index: int = Field(0, ge=0)


class InterviewAnswerResult(BaseModel):
    is_followup: bool = False
    followup_question: Optional[str] = None
    score: Optional[int] = None
    feedback: Optional[str] = None
    quality_label: Optional[str] = None
    quality_feedback: Optional[str] = None
    strengths: Optional[str] = None
    issues: Optional[str] = None
    improvement_suggestions: Optional[str] = None
    dimension_scores: Optional[Dict[str, Any]] = None
    # 评分校准：Agent(LLM) 评分与规则评分对照，用于评估 Agent 稳定性（进阶要求 #2）
    llm_score: Optional[int] = None
    rule_score: Optional[int] = None
    # 表达风险识别（基本要求 #15）：空泛表达 / 夸大绝对化表达
    vague_flags: List[str] = []
    biased_flags: List[str] = []
    next_question: Optional[str] = None
    current_index: int = 0
    total_questions: int = 8
    session_status: str = "in_progress"


class QuestionDetail(BaseModel):
    question: str
    first_answer: str = ""
    followup_question: Optional[str] = None
    followup_answer: Optional[str] = None
    scores: Optional[Dict[str, Any]] = None
    star_rewrite: Optional[str] = None


class StarSuggestion(BaseModel):
    question: str
    star_rewrite: str


class InterviewFinishResult(BaseModel):
    session_id: str
    interview_mode: str = "技术面"
    overall_score: float
    dimension_averages: Dict[str, float] = {}
    total_questions_answered: int = 0
    details: List[QuestionDetail] = []
    star_suggestions: List[StarSuggestion] = []
    practice_plan: str = ""
    summary: str = ""
    question_bank_summary: Dict[str, Any] = {}
    # 评分校准汇总：Agent 评分与规则评分的均值对照（进阶要求 #2）
    calibration_summary: Dict[str, Any] = {}
