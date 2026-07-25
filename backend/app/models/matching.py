from sqlalchemy import Column, DateTime, ForeignKey, Integer, Text, func
from sqlalchemy.orm import relationship

from app.db.session import Base


class MatchingRecord(Base):
    __tablename__ = "matching_records"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    resume_id = Column(
        Integer,
        ForeignKey("resumes.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    job_id = Column(
        Integer,
        ForeignKey("job_postings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    total_score = Column(Integer, nullable=False)
    details = Column(Text, default="{}", nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="matching_records")
    resume = relationship("Resume", back_populates="matching_records")
    job = relationship("JobPosting", back_populates="matching_records")
