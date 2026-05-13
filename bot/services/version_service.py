"""
VersionCheckBot - Telegram bot for monitoring software versions and CVE vulnerabilities

SPDX-License-Identifier: AGPL-3.0-or-later
Copyright (c) 2024 VersionCheckBot Contributors
"""
"""Service for checking software version EOL status via endoflife.date API."""
import aiohttp
import asyncio
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
from bot.utils.parser import _normalize_version
from config import settings

log = logging.getLogger(__name__)

cache_dir = Path(settings.CACHE_DIR)
cache_dir.mkdir(parents=True, exist_ok=True)

_cache = TTLCache(persistent_file=str(cache_dir / "eol_cache.json"))
_disk = cache_dir / "eol_products_cache_ru.json"


class VersionService:
    """
    Service for interacting with endoflife.date API.
    
    Provides methods to check software version EOL status, get release information,
    and format status messages for users.
    """
    
    _shared_instance: Optional["VersionService"] = None

    @classmethod
    def shared(cls) -> "VersionService":
        """Return a shared singleton instance to avoid session leaks."""
        if cls._shared_instance is None or (cls._shared_instance._sess and cls._shared_instance._sess.closed):
            cls._shared_instance = cls()
        return cls._shared_instance

    def __init__(self):
        self._sess: Optional[aiohttp.ClientSession] = None
        self._products: List[str] = []
        self._aliases: Dict[str, str] = {}
        self._prod_ts = 0

    async def _session(self) -> aiohttp.ClientSession:
        if not self._sess or self._sess.closed:
            connector = aiohttp.TCPConnector(limit=100, limit_per_host=30)
            self._sess = aiohttp.ClientSession(
                raise_for_status=True,
                timeout=aiohttp.ClientTimeout(total=8),
                connector=connector
            )
        return self._sess

    async def _fetch_json(self, path: str) -> Any:
        """Fetch JSON data from API with retry logic, rate limiting, and circuit breaker."""
        from bot.utils.api_rate_limiter import get_api_rate_limiter
        from bot.utils.circuit_breaker import CircuitBreaker, CircuitBreakerConfig
        
        rate_limiter = get_api_rate_limiter()
        await rate_limiter.wait_for_api("endoflife.date")
        
        if not hasattr(self, '_circuit_breaker'):
            self._circuit_breaker = CircuitBreaker(
                "endoflife.date",
                CircuitBreakerConfig(
                    failure_threshold=5,
                    timeout=60.0,
                    expected_exception=(aiohttp.ClientError, aiohttp.ServerTimeoutError, asyncio.TimeoutError)
                )
            )
        
        async def _fetch():
            sess = await self._session()
            url = f"{settings.API_ROOT.rstrip('/')}/{path.lstrip('/')}"
            log.debug(f"Fetching {url}")
            async with sess.get(url) as r:
                r.raise_for_status()
                return await r.json()
        
        async def fetch_with_cb():
            return await self._circuit_breaker.call(_fetch)
        
        return await retry_async(
            fetch_with_cb,
            max_attempts=DEFAULT_MAX_RETRIES,
            delay=DEFAULT_RETRY_DELAY,
            backoff=DEFAULT_RETRY_BACKOFF,
            exceptions=(aiohttp.ClientError, aiohttp.ServerTimeoutError, asyncio.TimeoutError)
        )

    async def products(self) -> List[str]:
        """Get list of available products."""
        if self._products and time.time() - self._prod_ts < settings.PRODUCTS_TTL:
            return self._products
        
        try:
            log.info("Fetching products list from API")
            data = await self._fetch_json("v1/products/")
            products, aliases = self._extract_products(data)
            self._products = products
            self._aliases = aliases
            self._prod_ts = time.time()
            
            try:
                _disk.write_text(json.dumps({
                    "ts": self._prod_ts,
                    "data": self._products,
                    "aliases": self._aliases
                }))
                log.info(f"Loaded {len(self._products)} products and saved to disk")
            except Exception as e:
                log.warning(f"Failed to save products to disk: {e}")
        except Exception as e:
            log.error(f"Failed to fetch products from API: {e}")
            if _disk.exists():
                try:
                    tmp = json.loads(_disk.read_text())
                    self._products = tmp["data"]
                    self._aliases = tmp.get("aliases", {})
                    self._prod_ts = tmp["ts"]
                    log.info(f"Loaded {len(self._products)} products from disk cache")
                except Exception as disk_err:
                    log.error(f"Failed to load products from disk: {disk_err}")
        
        return self._products

    def _extract_products(self, data: Any) -> tuple[List[str], Dict[str, str]]:
        """Extract product names and aliases from endoflife.date responses."""
        raw_products = data.get("result", data) if isinstance(data, dict) else data
        products: List[str] = []
        aliases: Dict[str, str] = {}

        for item in raw_products or []:
            if isinstance(item, dict):
                slug = item.get("name") or item.get("slug")
                item_aliases = item.get("aliases") or []
            else:
                slug = str(item)
                item_aliases = []

            if not slug:
                continue

            slug = str(slug).lower()
            products.append(slug)
            aliases[slug] = slug
            for alias in item_aliases:
                aliases[str(alias).lower()] = slug

        return products, aliases

    async def resolve_slug(self, slug: str) -> str:
        """Resolve a user-entered product name to a known endoflife.date slug."""
        normalized = slug.strip().lower()
        products = await self.products()

        if not products:
            return normalized

        canonical = self._aliases.get(normalized, normalized)
        if canonical in products:
            return canonical

        try:
            from rapidfuzz import fuzz, process
            match = process.extractOne(canonical, products, scorer=fuzz.WRatio)
            if match and match[1] >= 82:
                return match[0]
        except Exception:
            from difflib import get_close_matches
            matches = get_close_matches(canonical, products, n=1, cutoff=0.82)
            if matches:
                return matches[0]

        return canonical

    async def releases(self, slug: str) -> Optional[List[Dict]]:
        """Get release information for a product."""
        resolved_slug = await self.resolve_slug(slug)
        cached = await _cache.get(resolved_slug, settings.RELEASE_TTL)
        if cached is not None:
            return cached
        
        log.info(f"Fetching releases for {resolved_slug}")
        for variant in [f"v1/products/{resolved_slug}/", f"{resolved_slug}.json"]:
            try:
                data = await self._fetch_json(variant)
                releases = self._extract_releases(data)
                await _cache.set(resolved_slug, releases)
                log.info(f"Loaded {len(releases)} releases for {resolved_slug}")
                return releases
            except aiohttp.ClientResponseError as e:
                if e.status == 404:
                    continue
                log.warning(f"Error fetching {variant}: {e}")
            except Exception as e:
                log.warning(f"Unexpected error fetching {variant}: {e}")
                continue
        
        log.warning(f"Product {resolved_slug} not found in any variant")
        return None

    def _extract_releases(self, data: Any) -> List[Dict]:
        """Extract releases from both v1 and legacy API payloads."""
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            result = data.get("result", data)
            if isinstance(result, dict):
                releases = result.get("releases", [])
                return releases if isinstance(releases, list) else []
        return []

    async def close(self):
        """Close aiohttp session."""
        if self._sess and not self._sess.closed:
            await self._sess.close()

    def _eol_ru(self, eol_raw: Any, today: dt.date) -> str:
        """Format EOL date in Russian."""
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
        """Check if release is supported."""
        if "isMaintained" in rel:
            return bool(rel.get("isMaintained"))
        if "isEol" in rel:
            return not bool(rel.get("isEol"))

        eol_raw = rel.get("eol")
        if isinstance(eol_raw, bool):
            return not eol_raw
        if isinstance(eol_raw, str) and eol_raw:
            try:
                return dt.date.fromisoformat(eol_raw) >= dt.date.today()
            except ValueError:
                pass

        return str(rel.get('support') or rel.get('supported')).lower() in {
            "true", "yes", "active", "supported"
        }

    def _release_cycle(self, rel: Dict) -> str:
        return str(rel.get("cycle") or rel.get("name") or rel.get("releaseCycle") or "n/a")

    def _release_latest(self, rel: Dict) -> str:
        latest = rel.get("latest", "n/a")
        if isinstance(latest, dict):
            return str(latest.get("name") or latest.get("version") or "n/a")
        return str(latest)

    def _release_eol(self, rel: Dict) -> Any:
        return rel.get("eol") or rel.get("eolFrom")

    def _version_matches_release(self, version: Optional[str], rel: Dict) -> bool:
        if not version:
            return False

        query = _normalize_version(str(version))
        cycle = _normalize_version(self._release_cycle(rel))
        latest = _normalize_version(self._release_latest(rel))
        candidates = {cycle, latest}

        if query in candidates:
            return True
        if cycle and (query.startswith(f"{cycle}.") or query.startswith(f"{cycle}-")):
            return True
        if query and latest and latest.startswith(f"{query}."):
            return True
        if query and cycle and cycle.startswith(f"{query}."):
            return True

        return False

    def find_release(self, data: List[Dict], version: Optional[str]) -> Optional[Dict]:
        """Find the most relevant release for a possibly partial version query."""
        if not data:
            return None
        if version:
            for rel in data:
                if self._version_matches_release(version, rel):
                    return rel
        return data[0]

    def release_status(self, rel: Dict) -> str:
        """Return a stable status label for subscription monitoring."""
        if bool(rel.get("isEol")):
            return "eol"

        eol_raw = self._release_eol(rel)
        if isinstance(eol_raw, bool) and eol_raw:
            return "eol"
        if isinstance(eol_raw, str) and eol_raw:
            try:
                if dt.date.fromisoformat(eol_raw) < dt.date.today():
                    return "eol"
            except ValueError:
                pass

        if self._is_supported(rel):
            return "supported"
        return "unknown"

    async def status_line(self, slug: str, version: Optional[str]) -> str:
        """Get status line for a product/version."""
        display_slug = await self.resolve_slug(slug)
        data = await self.releases(display_slug)
        if data is None:
            return f"{EMOJI_CROSS} {slug}: не найдено"
        rel = self.find_release(data, version)
        if rel is None:
            return f"{EMOJI_CROSS} {slug}: не найдено"
        cycle = self._release_cycle(rel)
        latest = self._release_latest(rel)
        eol_desc = self._eol_ru(self._release_eol(rel), dt.date.today())
        sup_flag = EMOJI_CHECK if self._is_supported(rel) else EMOJI_CROSS
        return f"{sup_flag} {display_slug} {cycle} {EMOJI_ARROW} {latest} ({eol_desc})"

    def table(self, slug: str, data: List[Dict], highlight_version: Optional[str] = None, rows: int = DEFAULT_TABLE_ROWS) -> str:
        """Format release data as a markdown table."""
        head = f"*{slug} — релизы*\n```Релиз | Последний | Подд | EOL\n------ | -------- | ---- | ----------"
        lines = []
        highlight_low = highlight_version.lower() if highlight_version else ""
        for r in data[:rows]:
            rel = self._release_cycle(r)
            latest = self._release_latest(r)
            sup = "Да" if self._is_supported(r) else "Нет"
            eol = self._release_eol(r) or "—"
            marker = f"{EMOJI_MARKER} " if highlight_low and self._version_matches_release(highlight_low, r) else "  "
            lines.append(f"{marker}{rel:<6}| {latest:<8}| {sup:^3}| {eol}")
        return head + "\n" + "\n".join(lines) + "```"
