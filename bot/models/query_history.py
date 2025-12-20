"""Query history model."""
from sqlalchemy import Column, Integer, BigInteger, String, DateTime, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from bot.database.db import Base


class QueryHistory(Base):
    """Query history model for tracking user queries."""
    __tablename__ = "query_history"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(BigInteger, nullable=False, index=True)
    query_text = Column(Text, nullable=False)
    query_type = Column(String, nullable=False)  # "check", "cve", "subscribe", etc.
    result_summary = Column(Text, nullable=True)  # Brief summary of result
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    
    # Index for common queries
    __table_args__ = (
        {'sqlite_autoincrement': True}
    )

