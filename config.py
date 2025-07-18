import os, time
from dataclasses import dataclass

@dataclass(frozen=True)
class Settings:
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
    API_ROOT: str = os.getenv("EOL_API_ROOT", "https://endoflife.date/api")
    RELEASE_TTL: int = int(os.getenv("RELEASE_TTL", 6*60*60))   # 6h
    PRODUCTS_TTL: int = int(os.getenv("PRODUCTS_TTL", 24*60*60))
    MAX_PARALLEL: int = int(os.getenv("MAX_PARALLEL", 10))      # concurrent fetches

settings = Settings()
