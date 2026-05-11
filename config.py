"""Configuration management with validation."""
import os
import re
import logging
from dataclasses import dataclass
from typing import List, Optional
from pathlib import Path
from urllib.parse import urlparse

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Settings:
    """Application settings with validation."""
    
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
    API_ROOT: str = os.getenv("EOL_API_ROOT", "https://endoflife.date/api")
    NVD_API_KEY: str = os.getenv("NVD_API_KEY", "")
    NVD_API_ROOT: str = os.getenv("NVD_API_ROOT", "https://services.nvd.nist.gov/rest/json")
    CACHE_DIR: str = os.getenv("CACHE_DIR", "./cache")
    RELEASE_TTL: int = int(os.getenv("RELEASE_TTL", "21600"))
    PRODUCTS_TTL: int = int(os.getenv("PRODUCTS_TTL", "86400"))
    CVE_TTL: int = int(os.getenv("CVE_TTL", "43200"))
    MAX_PARALLEL: int = int(os.getenv("MAX_PARALLEL", "15"))
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./bot.db")
    SCHEDULER_INTERVAL: int = int(os.getenv("SCHEDULER_INTERVAL", "21600"))
    NOTIFICATION_ENABLED: bool = os.getenv("NOTIFICATION_ENABLED", "true").lower() == "true"
    ADMIN_IDS: List[int] = None
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    RATE_LIMIT_PER_MINUTE: int = int(os.getenv("RATE_LIMIT_PER_MINUTE", "20"))
    RATE_LIMIT_PER_HOUR: int = int(os.getenv("RATE_LIMIT_PER_HOUR", "200"))
    
    def __post_init__(self):
        self._validate_all()
    
    def _validate_all(self):
        self._validate_bot_token()
        self._validate_urls()
        self._validate_ttl_values()
        self._validate_database_url()
        self._validate_performance()
        self._validate_rate_limits()
        self._validate_log_level()
        self._parse_admin_ids()
        self._warn_about_issues()
    
    def _validate_bot_token(self):
        if not self.BOT_TOKEN:
            raise ValueError("BOT_TOKEN must be set")
        token_pattern = r'^\d+:[A-Za-z0-9_-]+$'
        if not re.match(token_pattern, self.BOT_TOKEN):
            log.warning("BOT_TOKEN format may be invalid. Expected format: number:alphanumeric")
    
    def _validate_urls(self):
        try:
            parsed = urlparse(self.API_ROOT)
            if not parsed.scheme or not parsed.netloc:
                raise ValueError(f"Invalid API_ROOT URL: {self.API_ROOT}")
        except Exception as e:
            raise ValueError(f"Invalid API_ROOT URL: {e}")
        
        try:
            parsed = urlparse(self.NVD_API_ROOT)
            if not parsed.scheme or not parsed.netloc:
                raise ValueError(f"Invalid NVD_API_ROOT URL: {self.NVD_API_ROOT}")
        except Exception as e:
            raise ValueError(f"Invalid NVD_API_ROOT URL: {e}")
    
    def _validate_ttl_values(self):
        min_ttl = 60
        max_ttl = 604800
        
        for name, value in [
            ("RELEASE_TTL", self.RELEASE_TTL),
            ("PRODUCTS_TTL", self.PRODUCTS_TTL),
            ("CVE_TTL", self.CVE_TTL)
        ]:
            if value < min_ttl:
                raise ValueError(f"{name} must be at least {min_ttl} seconds (1 minute)")
            if value > max_ttl:
                log.warning(f"{name} is very large ({value}s). Consider using a smaller value.")
    
    def _validate_database_url(self):
        if not self.DATABASE_URL:
            raise ValueError("DATABASE_URL must be set")
        if self.DATABASE_URL.startswith("sqlite:///"):
            return
        if self.DATABASE_URL.startswith("postgresql://") or self.DATABASE_URL.startswith("postgresql+psycopg2://"):
            try:
                parsed = urlparse(self.DATABASE_URL)
                if not parsed.netloc:
                    raise ValueError("Invalid PostgreSQL URL format")
            except Exception as e:
                raise ValueError(f"Invalid DATABASE_URL: {e}")
        else:
            log.warning(f"Unknown database type in DATABASE_URL: {self.DATABASE_URL}")
    
    def _validate_performance(self):
        if self.MAX_PARALLEL < 1:
            raise ValueError("MAX_PARALLEL must be at least 1")
        if self.MAX_PARALLEL > 100:
            log.warning(f"MAX_PARALLEL is very high ({self.MAX_PARALLEL}). This may cause rate limiting issues.")
        if self.SCHEDULER_INTERVAL < 60:
            raise ValueError("SCHEDULER_INTERVAL must be at least 60 seconds")
        if self.SCHEDULER_INTERVAL < 300:
            log.warning(f"SCHEDULER_INTERVAL is very short ({self.SCHEDULER_INTERVAL}s). This may cause high API usage.")
    
    def _validate_rate_limits(self):
        if self.RATE_LIMIT_PER_MINUTE < 1:
            raise ValueError("RATE_LIMIT_PER_MINUTE must be at least 1")
        if self.RATE_LIMIT_PER_HOUR < 1:
            raise ValueError("RATE_LIMIT_PER_HOUR must be at least 1")
        if self.RATE_LIMIT_PER_HOUR < self.RATE_LIMIT_PER_MINUTE * 10:
            log.warning("RATE_LIMIT_PER_HOUR should be at least 10x RATE_LIMIT_PER_MINUTE")
    
    def _validate_log_level(self):
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if self.LOG_LEVEL not in valid_levels:
            raise ValueError(f"Invalid LOG_LEVEL: {self.LOG_LEVEL}. Must be one of {valid_levels}")
    
    def _parse_admin_ids(self):
        admin_str = os.getenv("ADMIN_IDS", "")
        if admin_str:
            try:
                admin_ids = [int(x.strip()) for x in admin_str.split(",") if x.strip()]
                object.__setattr__(self, "ADMIN_IDS", admin_ids)
            except ValueError as e:
                log.warning(f"Failed to parse ADMIN_IDS: {e}")
                object.__setattr__(self, "ADMIN_IDS", [])
        else:
            object.__setattr__(self, "ADMIN_IDS", [])
    
    def _warn_about_issues(self):
        if not self.NVD_API_KEY:
            log.warning("NVD_API_KEY is not set. CVE features may be limited by rate limits.")
        if self.MAX_PARALLEL > 30 and not self.NVD_API_KEY:
            log.warning("High MAX_PARALLEL without NVD_API_KEY may cause rate limiting issues.")
        if self.SCHEDULER_INTERVAL < 3600:
            log.warning(f"Frequent scheduler runs ({self.SCHEDULER_INTERVAL}s) may increase API usage significantly.")


def validate_config() -> bool:
    """Validate configuration — triggers Settings instantiation."""
    _ = settings  # noqa: F841 — accessing forces __post_init__ validation
    return True


settings = Settings()
