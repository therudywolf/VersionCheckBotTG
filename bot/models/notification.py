"""Notification model."""
from sqlalchemy import Column, Integer, BigInteger, String, Text, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from bot.database.db import Base


class Notification(Base):
    """Notification model for tracking sent notifications."""
    __tablename__ = "notifications"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.user_id"), nullable=False, index=True)
    subscription_id = Column(Integer, ForeignKey("subscriptions.id"), nullable=True)
    message = Column(Text, nullable=False)
    notification_type = Column(String, nullable=False)  # "status_change", "new_cve", etc.
    sent_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    
    # Relationships
    user = relationship("User", backref="notifications")
    subscription = relationship("Subscription", backref="notifications")

