from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, Integer, String, func
from sqlalchemy.orm import relationship

from app.db.session import Base


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "role IN ('student', 'reviewer')",
            name="ck_users_role",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(64), unique=True, index=True, nullable=False)
    email = Column(String(128), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(32), default="student", nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    resumes = relationship("Resume", back_populates="user", cascade="all, delete-orphan")
    resume_audit_reports = relationship(
        "ResumeAuditReport",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    matching_records = relationship(
        "MatchingRecord",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    interview_sessions = relationship(
        "InterviewSession",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    reviewed_jobs = relationship("JobReviewRecord", back_populates="reviewer")
    agent_logs = relationship("AgentLog", back_populates="user")
