from sqlalchemy import Column, DateTime, Integer, String, Text, func

from app.db.session import Base


class ResumeAuditReport(Base):
    __tablename__ = "resume_audit_reports"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True, nullable=False)
    resume_text = Column(Text, nullable=False)
    score = Column(Integer, nullable=False)
    risk_flags = Column(Text, default="")
    suggestions = Column(Text, default="")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

