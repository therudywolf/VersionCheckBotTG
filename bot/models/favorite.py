"""Favorite product model."""
from sqlalchemy import Column, Integer, BigInteger, String, DateTime, ForeignKey, Index
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from bot.database.db import Base


class Favorite(Base):
    """Favorite product model for quick access."""
    __tablename__ = "favorites"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.user_id"), nullable=False, index=True)
    product_slug = Column(String, nullable=False, index=True)
    version = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationship
    user = relationship("User", backref="favorites")
    
    # Composite index
    __table_args__ = (
        Index('idx_user_product', 'user_id', 'product_slug', 'version'),
    )

