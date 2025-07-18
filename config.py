import os
from dataclasses import dataclass

@dataclass(frozen=True)
class Settings:
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
    CACHE_TTL: int = int(os.getenv("CACHE_TTL", 6 * 60 * 60))  # 6h
    API_BASE: str = os.getenv("EOL_API_BASE", "https://endoflife.date/api")
    DEBUG: bool = os.getenv("DEBUG", "0") == "1"

settings = Settings()
