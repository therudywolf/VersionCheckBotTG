"""Async client + cache layer around endoflife.date."""
import asyncio
import datetime as _dt
import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import aiohttp
from aiohttp import ClientSession

from config import settings

_log = logging.getLogger(__name__)

_PRODUCTS_CACHE_FILE = Path("/tmp/products_cache.json")
_PRODUCTS_TTL = 24 * 60 * 60  # 1 day

class EolService:
    def __init__(self) -> None:
        self._session: Optional[ClientSession] = None
        self._products: List[str] = []
        self._products_loaded_at: Optional[_dt.datetime] = None

    async def __aenter__(self):
        if not self._session:
            self._session = aiohttp.ClientSession(raise_for_status=True, timeout=aiohttp.ClientTimeout(total=10))
        await self._ensure_products()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if self._session and not self._session.closed:
            await self._session.close()

    async def _get_json(self, path: str) -> Any:
        url = f"{settings.API_BASE.rstrip('/')}/{path.lstrip('/')}"
        _log.debug("GET %s", url)
        async with self._session.get(url) as resp:
            return await resp.json()

    async def _ensure_products(self):
        need_refresh = not self._products_loaded_at or (_dt.datetime.utcnow() - self._products_loaded_at).total_seconds() > _PRODUCTS_TTL
        if self._products and not need_refresh:
            return
        try:
            products_json = await self._get_json("products.json")
            self._products = [item["slug"] if isinstance(item, dict) else item for item in products_json]
            self._products_loaded_at = _dt.datetime.utcnow()
            _PRODUCTS_CACHE_FILE.write_text(json.dumps({"ts": self._products_loaded_at.isoformat(), "data": self._products}))
        except Exception as e:
            _log.warning("Cannot load products.json, falling back: %s", e)
            if _PRODUCTS_CACHE_FILE.exists():
                data = json.loads(_PRODUCTS_CACHE_FILE.read_text())
                self._products = data["data"]
                self._products_loaded_at = _dt.datetime.fromisoformat(data["ts"])

    async def list_products(self) -> List[str]:
        await self._ensure_products()
        return self._products

    @lru_cache(maxsize=512)
    async def fetch_product(self, slug: str) -> Any:
        return await self._get_json(f"{slug}.json")

    async def get_status(self, slug: str, version: Optional[str] = None) -> str:
        try:
            data = await self.fetch_product(slug)
        except Exception as e:
            return f"❌ {slug}: {e}"

        today = _dt.date.today()
        release = None
        if version:
            vlow = version.lower()
            for rel in data:
                if vlow in {str(rel.get('cycle', '')).lower(), str(rel.get('latest', '')).lower()}:
                    release = rel
                    break
        if release is None:
            release = data[0]

        cycle = release.get('cycle') or release.get('releaseCycle', 'n/a')
        latest = release.get('latest', 'n/a')
        eol_raw = release.get('eol')

        # parse eol
        status_parts: List[str] = []
        eol_desc = self._render_eol(eol_raw, today)
        status_parts.append(eol_desc)

        support_raw = str(release.get('support') or release.get('supported')).lower()
        status_parts.insert(0, "поддерживается" if support_raw in {"true", "yes", "active", "supported"} else "не поддерживается")

        return f"🔹 {slug} {cycle} → {latest} ({', '.join(status_parts)})"

    @staticmethod
    def _render_eol(eol_val: Any, today: _dt.date) -> str:
        if isinstance(eol_val, str) and eol_val:
            try:
                eol_dt = _dt.date.fromisoformat(eol_val)
                if eol_dt < today:
                    return "EOL"
                days = (eol_dt - today).days
                return f"EOL через {days // 365}y{(days % 365)//30}m"
            except ValueError:
                return f"EOL: {eol_val}"
        return "дата EOL не указана"
