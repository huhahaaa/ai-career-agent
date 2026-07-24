from typing import List

from pydantic import BaseModel


class InterviewStartRequest(BaseModel):
    resume_text: str
    target_job_id: str = ""
    target_position: str = ""


class InterviewQuestion(BaseModel):
    session_id: str
    question: str
    tools_used: List[str]


class InterviewAnswerRequest(BaseModel):
    answer: str


class InterviewAnswerResult(BaseModel):
    score: int
    feedback: str
    next_question: str

