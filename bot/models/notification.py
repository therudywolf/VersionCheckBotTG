"""
VersionCheckBot - Telegram bot for monitoring software versions and CVE vulnerabilities

SPDX-License-Identifier: AGPL-3.0-or-later
Copyright (c) 2024 VersionCheckBot Contributors
"""
"""Notification model."""
from sqlalchemy import Column, Integer, BigInteger, String, Text, DateTime, ForeignKey, Index
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from bot.database.db import Base


class Notification(Base):
    """Notification model for tracking sent notifications."""
    __tablename__ = "notifications"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.user_id"), nullable=False, index=True)
    subscription_id = Column(Integer, ForeignKey("subscriptions.id"), nullable=True, index=True)
    message = Column(Text, nullable=False)
    notification_type = Column(String, nullable=False, index=True)  # "status_change", "new_cve", etc.
    sent_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    
    # Relationships
    user = relationship("User", backref="notifications")
    subscription = relationship("Subscription", backref="notifications")
    
    # Composite indexes for common queries
    __table_args__ = (
        Index('idx_user_type', 'user_id', 'notification_type'),
        Index('idx_user_sent', 'user_id', 'sent_at'),
        Index('idx_subscription_type', 'subscription_id', 'notification_type'),
    )

