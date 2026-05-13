"""
VersionCheckBot - Telegram bot for monitoring software versions and CVE vulnerabilities

SPDX-License-Identifier: AGPL-3.0-or-later
Copyright (c) 2024 VersionCheckBot Contributors
"""
"""CVE record model."""
from sqlalchemy import Column, Integer, String, DateTime, Text, Index
from sqlalchemy.sql import func
from bot.database.db import Base


class CVERecord(Base):
    """CVE record model for caching CVE data."""
    __tablename__ = "cve_records"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    cve_id = Column(String, nullable=False, index=True)
    product = Column(String, nullable=False, index=True)
    version = Column(String, nullable=True, index=True)
    severity = Column(String, nullable=True)  # "CRITICAL", "HIGH", "MEDIUM", "LOW"
    description = Column(Text, nullable=True)
    published_date = Column(DateTime(timezone=True), nullable=True)
    last_modified = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Indexes for faster lookups
    __table_args__ = (
        Index('idx_product_version', 'product', 'version'),
        Index('idx_severity', 'severity'),
        Index('idx_published_date', 'published_date'),
        Index('idx_product_severity', 'product', 'severity'),
    )

