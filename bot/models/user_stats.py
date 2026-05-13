"""
VersionCheckBot - Telegram bot for monitoring software versions and CVE vulnerabilities

SPDX-License-Identifier: AGPL-3.0-or-later
Copyright (c) 2024 VersionCheckBot Contributors
"""
"""User statistics model."""
from sqlalchemy import Column, Integer, BigInteger, String, DateTime, Integer as SQLInteger
from sqlalchemy.sql import func
from bot.database.db import Base


class UserStats(Base):
    """User statistics for tracking usage."""
    __tablename__ = "user_stats"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(BigInteger, nullable=False, unique=True, index=True)
    
    # Command usage
    commands_count = Column(SQLInteger, default=0)
    check_commands = Column(SQLInteger, default=0)
    subscribe_commands = Column(SQLInteger, default=0)
    cve_commands = Column(SQLInteger, default=0)
    
    # Last activity
    last_command = Column(String, nullable=True)
    last_activity = Column(DateTime(timezone=True), nullable=True)
    
    # First seen
    first_seen = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())



