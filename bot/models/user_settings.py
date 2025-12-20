"""User settings model."""
from sqlalchemy import Column, Integer, BigInteger, String, Boolean, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from bot.database.db import Base


class UserSettings(Base):
    """User settings model for notification preferences."""
    __tablename__ = "user_settings"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.user_id"), nullable=False, unique=True, index=True)
    
    # Notification settings
    notify_status_change = Column(Boolean, default=True)
    notify_new_cve = Column(Boolean, default=True)
    notify_eol_warning = Column(Boolean, default=True)
    notify_only_critical_cve = Column(Boolean, default=False)  # Only critical CVE if True
    
    # Other settings
    language = Column(String, default="ru")
    
    # Relationship
    user = relationship("User", backref="settings", uselist=False)

