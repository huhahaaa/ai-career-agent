from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import relationship

from app.db.session import Base

RESUME_SOURCE_FORMAL = "formal"
RESUME_SOURCE_MATCHING_SNAPSHOT = "matching_snapshot"
RESUME_SOURCE_INTERVIEW_SNAPSHOT = "interview_snapshot"
RESUME_SNAPSHOT_SOURCES = {
    RESUME_SOURCE_MATCHING_SNAPSHOT,
    RESUME_SOURCE_INTERVIEW_SNAPSHOT,
}


class Resume(Base):
    __tablename__ = "resumes"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title = Column(String(128), nullable=False)
    current_version_number = Column(Integer, default=1, nullable=False)
    source_type = Column(
        String(32),
        default=RESUME_SOURCE_FORMAL,
        nullable=False,
        index=True,
    )
    is_default = Column(Boolean, default=False, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    user = relationship("User", back_populates="resumes")
    versions = relationship(
        "ResumeVersion",
        back_populates="resume",
        cascade="all, delete-orphan",
        order_by="ResumeVersion.version_number",
    )
    audit_reports = relationship(
        "ResumeAuditReport",
        back_populates="resume",
        cascade="all, delete-orphan",
    )
    matching_records = relationship("MatchingRecord", back_populates="resume")
    interview_sessions = relationship("InterviewSession", back_populates="resume")


class ResumeVersion(Base):
    __tablename__ = "resume_versions"
    __table_args__ = (
        UniqueConstraint(
            "resume_id",
            "version_number",
            name="uq_resume_versions_resume_version",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    resume_id = Column(
        Integer,
        ForeignKey("resumes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version_number = Column(Integer, nullable=False)
    file_name = Column(String(255), default="", nullable=False)
    file_path = Column(String(512), default="", nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    resume = relationship("Resume", back_populates="versions")


class ResumeAuditReport(Base):
    __tablename__ = "resume_audit_reports"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    resume_id = Column(
        Integer,
        ForeignKey("resumes.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    score = Column(Integer, nullable=False)
    risk_flags = Column(Text, default="[]", nullable=False)
    suggestions = Column(Text, default="[]", nullable=False)
    missing_keywords = Column(Text, default="[]", nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="resume_audit_reports")
    resume = relationship("Resume", back_populates="audit_reports")
