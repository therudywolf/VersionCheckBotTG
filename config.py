import os
from dataclasses import dataclass

@dataclass(frozen=True)
class Settings:
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
    API_ROOT: str = os.getenv("EOL_API_ROOT", "https://endoflife.date/api")
    CACHE_TTL: int = int(os.getenv("CACHE_TTL", 21600))
    PRODUCTS_TTL: int = int(os.getenv("PRODUCTS_TTL", 86400))
    DEBUG: bool = os.getenv("DEBUG", "0") == "1"

settings = Settings()
