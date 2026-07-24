from sqlalchemy import Column, DateTime, Integer, String, Text, func

from app.db.session import Base


class JobPosting(Base):
    __tablename__ = "job_postings"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(128), index=True, nullable=False)
    company = Column(String(128), index=True, nullable=False)
    location = Column(String(128), nullable=False)
    publish_time = Column(String(64), nullable=False)
    skills = Column(Text, nullable=False)
    source_link = Column(String(512), nullable=False)
    status = Column(String(32), default="pending", index=True, nullable=False)
    audit_comment = Column(Text, default="")
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

