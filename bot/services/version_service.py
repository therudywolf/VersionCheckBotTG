"""Service for checking software version EOL status via endoflife.date API."""
import aiohttp
import time
import logging
import json
import datetime as dt
from pathlib import Path
from typing import Any, Dict, List, Optional

from bot.utils.cache import TTLCache
from bot.utils.retry import retry_async
from bot.utils.constants import (
    EMOJI_CHECK, EMOJI_CROSS, EMOJI_ARROW, EMOJI_MARKER,
    DEFAULT_TABLE_ROWS, DEFAULT_MAX_RETRIES, DEFAULT_RETRY_DELAY, DEFAULT_RETRY_BACKOFF
)
from config import settings

log = logging.getLogger(__name__)
import asyncio
_cache = TTLCache(persistent_file="/tmp/eol_cache.json")
_disk = Path("/tmp/eol_products_cache_ru.json")


class VersionService:
    """
    Service for interacting with endoflife.date API.
    
    Provides methods to check software version EOL status, get release information,
    and format status messages for users.
    
    Example:
        ```python
        service = VersionService()
        releases = await service.releases("python")
        status = await service.status_line("python", "3.11")
        ```
    """
    
    def __init__(self):
        """
        Initialize VersionService.
        
        Creates empty session and product list. Session is created lazily on first use.
        """
        self._sess: Optional[aiohttp.ClientSession] = None
        self._products: List[str] = []
        self._prod_ts = 0

    async def _session(self) -> aiohttp.ClientSession:
        """
        Get or create aiohttp session.
        
        Returns:
            aiohttp.ClientSession instance
        """
        if not self._sess:
            self._sess = aiohttp.ClientSession(
                raise_for_status=True,
                timeout=aiohttp.ClientTimeout(total=8)
            )
        return self._sess

    async def _fetch_json(self, path: str) -> Any:
        """
        Fetch JSON data from API with retry logic.
        
        Args:
            path: API path (relative to API_ROOT)
            
        Returns:
            Parsed JSON data
            
        Raises:
            aiohttp.ClientError: If request fails after retries
        """
        async def _fetch():
            sess = await self._session()
            url = f"{settings.API_ROOT.rstrip('/')}/{path.lstrip('/')}"
            log.debug(f"Fetching {url}")
            async with sess.get(url) as r:
                r.raise_for_status()
                return await r.json()
        
        return await retry_async(
            _fetch,
            max_attempts=DEFAULT_MAX_RETRIES,
            delay=DEFAULT_RETRY_DELAY,
            backoff=DEFAULT_RETRY_BACKOFF,
            exceptions=(aiohttp.ClientError, aiohttp.ServerTimeoutError, asyncio.TimeoutError)
        )

    async def products(self) -> List[str]:
        """
        Get list of available products.
        
        Returns:
            List of product slugs
        """
        if self._products and time.time() - self._prod_ts < settings.PRODUCTS_TTL:
            log.debug(f"Returning cached products list ({len(self._products)} items)")
            return self._products
        
        try:
            log.info("Fetching products list from API")
            data = await self._fetch_json("products.json")
            self._products = [d["slug"] if isinstance(d, dict) else d for d in data]
            self._prod_ts = time.time()
            
            # Save to disk
            try:
                _disk.write_text(json.dumps({"ts": self._prod_ts, "data": self._products}))
                log.info(f"Loaded {len(self._products)} products and saved to disk")
            except Exception as e:
                log.warning(f"Failed to save products to disk: {e}")
        except Exception as e:
            log.error(f"Failed to fetch products from API: {e}")
            # Try to load from disk
            if _disk.exists():
                try:
                    tmp = json.loads(_disk.read_text())
                    self._products = tmp["data"]
                    self._prod_ts = tmp["ts"]
                    log.info(f"Loaded {len(self._products)} products from disk cache")
                except Exception as disk_err:
                    log.error(f"Failed to load products from disk: {disk_err}")
        
        return self._products

    async def releases(self, slug: str) -> Optional[List[Dict]]:
        """
        Get release information for a product.
        
        Args:
            slug: Product slug
            
        Returns:
            List of release dictionaries or None if not found
        """
        cached = await _cache.get(slug, settings.RELEASE_TTL)
        if cached is not None:
            log.debug(f"Returning cached releases for {slug}")
            return cached
        
        log.info(f"Fetching releases for {slug}")
        for variant in [f"v1/{slug}.json", f"{slug}.json"]:
            try:
                data = await self._fetch_json(variant)
                await _cache.set(slug, data)
                log.info(f"Loaded {len(data)} releases for {slug}")
                return data
            except aiohttp.ClientResponseError as e:
                if e.status == 404:
                    log.debug(f"Product {slug} not found at {variant}")
                    continue
                log.warning(f"Error fetching {variant}: {e}")
            except Exception as e:
                log.warning(f"Unexpected error fetching {variant}: {e}")
                continue
        
        log.warning(f"Product {slug} not found in any variant")
        return None

    async def close(self):
        """Close aiohttp session."""
        if self._sess and not self._sess.closed:
            await self._sess.close()

    def _eol_ru(self, eol_raw: Any, today: dt.date) -> str:
        """
        Format EOL date in Russian.
        
        Args:
            eol_raw: Raw EOL date (string or None)
            today: Today's date
            
        Returns:
            Formatted EOL string in Russian
        """
        if isinstance(eol_raw, str) and eol_raw:
            try:
                dt_obj = dt.date.fromisoformat(eol_raw)
                diff = (dt_obj - today).days
                if diff < 0:
                    return "EOL"
                years = diff // 365
                months = (diff % 365) // 30
                return f"EOL через {years}г{months}м"
            except ValueError:
                return f"EOL: {eol_raw}"
        return "дата EOL не указана"

    def _is_supported(self, rel: Dict) -> bool:
        """
        Check if release is supported.
        
        Args:
            rel: Release dictionary
            
        Returns:
            True if supported, False otherwise
        """
        return str(rel.get('support') or rel.get('supported')).lower() in {
            "true", "yes", "active", "supported"
        }

    async def status_line(self, slug: str, version: Optional[str]) -> str:
        """
        Get status line for a product/version.
        
        Args:
            slug: Product slug
            version: Optional version string
            
        Returns:
            Formatted status line
        """
        data = await self.releases(slug)
        if data is None:
            return f"{EMOJI_CROSS} {slug}: не найдено"
        rel = None
        if version:
            v = version.lower()
            for r in data:
                if v in {str(r.get('cycle', '')).lower(), str(r.get('latest', '')).lower()}:
                    rel = r
                    break
        if rel is None:
            rel = data[0]
        cycle = rel.get('cycle') or rel.get('releaseCycle', 'n/a')
        latest = rel.get('latest', 'n/a')
        eol_desc = self._eol_ru(rel.get('eol'), dt.date.today())
        sup_flag = EMOJI_CHECK if self._is_supported(rel) else EMOJI_CROSS
        return f"{sup_flag} {slug} {cycle} {EMOJI_ARROW} {latest} ({eol_desc})"

    def table(self, slug: str, data: List[Dict], highlight_version: Optional[str] = None, rows: int = DEFAULT_TABLE_ROWS) -> str:
        """
        Format release data as a markdown table.
        
        Args:
            slug: Product slug
            data: List of release dictionaries
            highlight_version: Optional version to highlight
            rows: Maximum number of rows to show
            
        Returns:
            Formatted markdown table string
        """
        head = f"*{slug} — релизы*\n```Релиз | Последний | Подд | EOL\n------ | -------- | ---- | ----------"
        lines = []
        highlight_low = highlight_version.lower() if highlight_version else ""
        for r in data[:rows]:
            rel = str(r.get('cycle') or r.get('releaseCycle', '?'))
            latest = str(r.get('latest', '?'))
            sup = "Да" if self._is_supported(r) else "Нет"
            eol = r.get('eol') or "—"
            marker = f"{EMOJI_MARKER} " if highlight_low and highlight_low in {rel.lower(), latest.lower()} else "  "
            lines.append(f"{marker}{rel:<6}| {latest:<8}| {sup:^3}| {eol}")
        return head + "\n" + "\n".join(lines) + "```"

