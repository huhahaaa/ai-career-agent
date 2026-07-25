from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import relationship

from app.db.session import Base


class AgentLog(Base):
    __tablename__ = "agent_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    operation = Column(String(128), nullable=False, index=True)
    status = Column(String(32), nullable=False, index=True)
    duration_ms = Column(Integer, nullable=True)
    request_summary = Column(Text, default="", nullable=False)
    response_summary = Column(Text, default="", nullable=False)
    error_message = Column(Text, default="", nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="agent_logs")
