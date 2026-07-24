from sqlalchemy import Column, DateTime, Integer, String, Text, func

from app.db.session import Base


class InterviewSession(Base):
    __tablename__ = "interview_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True, nullable=False)
    target_job_id = Column(Integer, index=True, nullable=True)
    current_question = Column(Text, nullable=False)
    status = Column(String(32), default="running", nullable=False)
    score = Column(Integer, nullable=True)
    feedback = Column(Text, default="")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

