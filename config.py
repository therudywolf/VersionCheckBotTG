"""Configuration management with validation."""
import os
from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class Settings:
    """Application settings with validation."""
    
    # Telegram Bot
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
    
    # API Configuration
    API_ROOT: str = os.getenv("EOL_API_ROOT", "https://endoflife.date/api")
    NVD_API_KEY: str = os.getenv("NVD_API_KEY", "")
    NVD_API_ROOT: str = os.getenv("NVD_API_ROOT", "https://services.nvd.nist.gov/rest/json")
    
    # Cache Configuration
    RELEASE_TTL: int = int(os.getenv("RELEASE_TTL", "21600"))  # 6 hours
    PRODUCTS_TTL: int = int(os.getenv("PRODUCTS_TTL", "86400"))  # 24 hours
    CVE_TTL: int = int(os.getenv("CVE_TTL", "43200"))  # 12 hours
    
    # Performance
    MAX_PARALLEL: int = int(os.getenv("MAX_PARALLEL", "15"))
    
    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./bot.db")
    
    # Scheduler
    SCHEDULER_INTERVAL: int = int(os.getenv("SCHEDULER_INTERVAL", "21600"))  # 6 hours
    NOTIFICATION_ENABLED: bool = os.getenv("NOTIFICATION_ENABLED", "true").lower() == "true"
    
    # Admin
    ADMIN_IDS: List[int] = None
    
    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    
    def __post_init__(self):
        """Validate settings after initialization."""
        if not self.BOT_TOKEN:
            raise ValueError("BOT_TOKEN must be set")
        
        if self.MAX_PARALLEL < 1:
            raise ValueError("MAX_PARALLEL must be at least 1")
        
        if self.SCHEDULER_INTERVAL < 60:
            raise ValueError("SCHEDULER_INTERVAL must be at least 60 seconds")
        
        if self.LOG_LEVEL not in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
            raise ValueError(f"Invalid LOG_LEVEL: {self.LOG_LEVEL}")
        
        # Parse ADMIN_IDS
        admin_str = os.getenv("ADMIN_IDS", "")
        if admin_str:
            try:
                admin_ids = [int(x.strip()) for x in admin_str.split(",") if x.strip()]
                object.__setattr__(self, "ADMIN_IDS", admin_ids)
            except ValueError:
                object.__setattr__(self, "ADMIN_IDS", [])
        else:
            object.__setattr__(self, "ADMIN_IDS", [])


settings = Settings()
