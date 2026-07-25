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


class JobPosting(Base):
    __tablename__ = "job_postings"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'approved', 'rejected')",
            name="ck_job_postings_status",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(128), index=True, nullable=False)
    company = Column(String(128), index=True, nullable=False)
    location = Column(String(128), nullable=False)
    salary_range = Column(String(64), default="", nullable=False)
    education = Column(String(64), default="", nullable=False)
    experience = Column(String(64), default="", nullable=False)
    responsibilities = Column(Text, default="", nullable=False)
    requirements = Column(Text, default="", nullable=False)
    publish_time = Column(String(64), nullable=False)
    skills = Column(Text, nullable=False)
    source_site = Column(String(128), default="", nullable=False)
    source_link = Column(String(512), unique=True, index=True, nullable=False)
    status = Column(String(32), default="pending", index=True, nullable=False)
    audit_comment = Column(Text, default="", nullable=False)
    collected_at = Column(DateTime(timezone=True), server_default=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    review_records = relationship(
        "JobReviewRecord",
        back_populates="job",
        cascade="all, delete-orphan",
    )
    matching_records = relationship("MatchingRecord", back_populates="job")
    interview_sessions = relationship("InterviewSession", back_populates="target_job")


class JobReviewRecord(Base):
    __tablename__ = "job_review_records"
    __table_args__ = (
        CheckConstraint(
            "decision IN ('approved', 'rejected')",
            name="ck_job_review_records_decision",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(
        Integer,
        ForeignKey("job_postings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    reviewer_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    decision = Column(String(32), nullable=False)
    comment = Column(Text, default="", nullable=False)
    reviewed_at = Column(DateTime(timezone=True), server_default=func.now())

    job = relationship("JobPosting", back_populates="review_records")
    reviewer = relationship("User", back_populates="reviewed_jobs")
