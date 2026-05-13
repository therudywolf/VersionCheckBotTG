"""
VersionCheckBot - Telegram bot for monitoring software versions and CVE vulnerabilities

SPDX-License-Identifier: AGPL-3.0-or-later
Copyright (c) 2024 VersionCheckBot Contributors
"""
"""Subscription model."""
from sqlalchemy import Column, Integer, BigInteger, String, DateTime, Boolean, ForeignKey, Index
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from bot.database.db import Base


class Subscription(Base):
    """Subscription model for monitoring products/versions."""
    __tablename__ = "subscriptions"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.user_id"), nullable=False, index=True)
    product_slug = Column(String, nullable=False, index=True)
    version = Column(String, nullable=True)
    last_status = Column(String, nullable=True)  # "supported", "eol", etc.
    last_checked = Column(DateTime(timezone=True), nullable=True, index=True)
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationship
    user = relationship("User", backref="subscriptions")
    
    # Composite indexes for common queries
    __table_args__ = (
        Index('idx_user_active', 'user_id', 'is_active'),
        Index('idx_product_version', 'product_slug', 'version'),
        Index('idx_last_checked', 'last_checked'),
    )

