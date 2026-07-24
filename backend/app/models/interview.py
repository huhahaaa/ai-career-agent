from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import relationship

from app.db.session import Base


class InterviewSession(Base):
    __tablename__ = "interview_sessions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('running', 'completed', 'cancelled', 'failed')",
            name="ck_interview_sessions_status",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    target_job_id = Column(
        Integer,
        ForeignKey("job_postings.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    resume_id = Column(
        Integer,
        ForeignKey("resumes.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    current_question = Column(Text, default="", nullable=False)
    status = Column(String(32), default="running", nullable=False)
    score = Column(Integer, nullable=True)
    feedback = Column(Text, default="", nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    user = relationship("User", back_populates="interview_sessions")
    target_job = relationship("JobPosting", back_populates="interview_sessions")
    resume = relationship("Resume", back_populates="interview_sessions")
    messages = relationship(
        "InterviewMessage",
        back_populates="session",
        cascade="all, delete-orphan",
    )


class InterviewMessage(Base):
    __tablename__ = "interview_messages"
    __table_args__ = (
        CheckConstraint(
            "role IN ('system', 'assistant', 'user')",
            name="ck_interview_messages_role",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(
        Integer,
        ForeignKey("interview_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role = Column(String(32), nullable=False)
    content = Column(Text, nullable=False)
    score = Column(Integer, nullable=True)
    feedback = Column(Text, default="", nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    session = relationship("InterviewSession", back_populates="messages")
