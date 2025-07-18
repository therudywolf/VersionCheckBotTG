"""API client with dual‑path fallback."""
import aiohttp, datetime as _dt, json, logging
from pathlib import Path
from functools import lru_cache
from typing import Any, List, Optional
from config import settings

log = logging.getLogger(__name__)
_CACHE_FILE = Path("/tmp/eol_products_cache.json")

class Eol:
    def __init__(self):
        self._session: Optional[aiohttp.ClientSession] = None
        self._products: List[str] = []
        self._loaded: Optional[_dt.datetime] = None

    async def _get(self, path: str) -> Any:
        if not self._session:
            self._session = aiohttp.ClientSession(raise_for_status=True, timeout=aiohttp.ClientTimeout(total=10))
        url = f"{settings.API_ROOT.rstrip('/')}/{path.lstrip('/')}"
        async with self._session.get(url) as r:
            return await r.json()

    async def list_products(self) -> List[str]:
        if self._products and (_dt.datetime.utcnow() - self._loaded).total_seconds() < settings.PRODUCTS_TTL:
            return self._products
        try:
            data = await self._get("products.json")
            self._products = [d["slug"] if isinstance(d, dict) else d for d in data]
            self._loaded = _dt.datetime.utcnow()
            _CACHE_FILE.write_text(json.dumps({"ts": self._loaded.isoformat(), "data": self._products}))
        except Exception as e:
            log.warning("products.json error (%s), use fallback", e)
            if _CACHE_FILE.exists():
                cached = json.loads(_CACHE_FILE.read_text())
                self._products = cached["data"]
                self._loaded = _dt.datetime.fromisoformat(cached["ts"])
        return self._products

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    @lru_cache(maxsize=512)
    async def fetch(self, slug: str):
        # try v1 first, then root
        try:
            return await self._get(f"v1/{slug}.json")
        except Exception:
            return await self._get(f"{slug}.json")

    async def status(self, slug: str, ver: Optional[str]=None) -> str:
        try:
            releases = await self.fetch(slug)
        except Exception as e:
            return f"❌ {slug}: {e}"
        today = _dt.date.today()
        sel = None
        if ver:
            vlow = ver.lower()
            for r in releases:
                if vlow in {str(r.get('cycle','')).lower(), str(r.get('latest','')).lower()}:
                    sel = r
                    break
        if sel is None:
            sel = releases[0]

        cycle = sel.get('cycle') or sel.get('releaseCycle', 'n/a')
        latest = sel.get('latest', 'n/a')
        eol = sel.get('eol')
        desc = self._eol_desc(eol, today)
        support = str(sel.get('support') or sel.get('supported')).lower() in {"true","yes","active","supported"}
        return f"🔹 {slug} {cycle} → {latest} ({'поддерживается' if support else 'не поддерживается'}, {desc})"

    @staticmethod
    def _eol_desc(eol, today):
        import datetime as _dt
        if isinstance(eol, str) and eol:
            try:
                dt = _dt.date.fromisoformat(eol)
                if dt < today:
                    return "EOL"
                days = (dt - today).days
                return f"EOL через {days//365}y{(days%365)//30}m"
            except ValueError:
                return f"EOL: {eol}"
        return "дата EOL не указана"
