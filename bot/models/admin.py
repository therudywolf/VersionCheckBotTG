"""Admin and access management model."""
from sqlalchemy import Column, Integer, BigInteger, String, DateTime, Boolean
from sqlalchemy.sql import func
from bot.database.db import Base


class Access(Base):
    """Access model for managing user access to bot."""
    __tablename__ = "access"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(BigInteger, nullable=False, unique=True, index=True)
    has_access = Column(Boolean, default=True, index=True)  # Has access to bot
    is_admin = Column(Boolean, default=False, index=True)  # Is admin
    granted_by = Column(BigInteger, nullable=True)  # Who granted access
    granted_at = Column(DateTime(timezone=True), server_default=func.now())
    notes = Column(String, nullable=True)  # Optional notes


class BotMode(Base):
    """Bot mode settings."""
    __tablename__ = "bot_mode"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    mode = Column(String, nullable=False, default="open")  # "open" or "restricted"
    changed_by = Column(BigInteger, nullable=True)
    changed_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

