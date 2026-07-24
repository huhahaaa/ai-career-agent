from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field


class InterviewStartRequest(BaseModel):
    resume_text: str = Field(..., min_length=10)
    target_job_id: Optional[Union[int, str]] = None
    target_position: str = ""


class InterviewQuestion(BaseModel):
    session_id: str
    question: str
    tools_used: List[str] = []
    total_questions: int = 8


class InterviewAnswerRequest(BaseModel):
    answer: str = Field(..., min_length=1)
    question_index: int = Field(0, ge=0)


class InterviewAnswerResult(BaseModel):
    is_followup: bool = False
    followup_question: Optional[str] = None
    score: Optional[int] = None
    feedback: Optional[str] = None
    dimension_scores: Optional[Dict[str, Any]] = None
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
    overall_score: float
    dimension_averages: Dict[str, float] = {}
    total_questions_answered: int = 0
    details: List[QuestionDetail] = []
    star_suggestions: List[StarSuggestion] = []
    practice_plan: str = ""
    summary: str = ""
