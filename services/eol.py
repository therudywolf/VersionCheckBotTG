"""Async API client for endoflife.date with smart cache + pretty helpers."""
from __future__ import annotations

import json
import logging
import time
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiohttp

from config import settings
from utils.cache import TTLCache

_log = logging.getLogger(__name__)
_cache = TTLCache()
_PRODUCTS_CACHE = Path("/tmp/eol_products.json")


class EolService:
    """Encapsulates calls to endoflife.date API."""

    def __init__(self) -> None:
        self._session: aiohttp.ClientSession | None = None
        self._products: list[str] = []
        self._products_ts = 0.0

    # --------------------------------------------------------------------- #
    # internals
    async def _client(self) -> aiohttp.ClientSession:
        if not self._session:
            self._session = aiohttp.ClientSession(
                raise_for_status=True,
                timeout=aiohttp.ClientTimeout(total=10),
            )
        return self._session

    async def _get_json(self, path: str) -> Any:
        url = f"{settings.API_ROOT.rstrip('/')}/{path.lstrip('/')}"
        async with (await self._client()).get(url) as resp:
            return await resp.json()

    # --------------------------------------------------------------------- #
    # public API
    async def product_slugs(self) -> list[str]:
        """Return list of available slugs (cached)."""
        if self._products and time.time() - self._products_ts < settings.PRODUCTS_TTL:
            return self._products
        try:
            data = await self._get_json("products.json")
            self._products = [item["slug"] if isinstance(item, dict) else item for item in data]
            self._products_ts = time.time()
            _PRODUCTS_CACHE.write_text(json.dumps({"ts": self._products_ts, "data": self._products}))
        except Exception as exc:  # noqa: BLE001
            _log.warning("products.json failed: %s", exc)
            if _PRODUCTS_CACHE.exists():
                cached = json.loads(_PRODUCTS_CACHE.read_text())
                self._products = cached["data"]
                self._products_ts = cached["ts"]
        return self._products

    async def releases(self, slug: str) -> Optional[list[dict]]:
        """Get release list with TTL cache and dual‑path fallback."""
        cached = await _cache.get(slug, settings.RELEASE_TTL)
        if cached is not None:
            return cached
        for variant in (f"v1/{slug}.json", f"{slug}.json"):
            try:
                data = await self._get_json(variant)
                await _cache.set(slug, data)
                return data
            except Exception:
                continue
        return None

    # ------------------------------------------------------------------ #
    # formatting helpers
    @staticmethod
    def _supported(rel: dict) -> bool:
        return str(rel.get("support") or rel.get("supported")).lower() in {
            "true",
            "yes",
            "active",
            "supported",
        }

    @staticmethod
    def _eol_desc(raw: Any, today: date) -> str:
        if isinstance(raw, str) and raw:
            try:
                eol_dt = date.fromisoformat(raw)
                delta = (eol_dt - today).days
                if delta < 0:
                    return "EOL"
                years, months = divmod(delta, 365)
                months //= 30
                return f"EOL через {years}г{months}м"
            except ValueError:
                return f"EOL: {raw}"
        return "дата EOL не указана"

    async def status_line(self, slug: str, version: str | None) -> str:
        data = await self.releases(slug)
        if data is None:
            return f"❌ {slug}: не найдено"

        rel = None
        if version:
            v_low = version.lower()
            for r in data:
                if v_low in {str(r.get("cycle", "")).lower(), str(r.get("latest", "")).lower()}:
                    rel = r
                    break
        if rel is None:
            rel = data[0]

        cycle = rel.get("cycle") or rel.get("releaseCycle", "?")
        latest = rel.get("latest", "?")
        today = date.today()
        icon = "✅" if self._supported(rel) else "❌"
        return f"{icon} {slug} {cycle} → {latest} ({self._eol_desc(rel.get('eol'), today)})"

    def table(
        self, slug: str, data: list[dict], highlight: str | None = None, rows: int = 7
    ) -> str:
        """Pretty Unicode table with optional row highlight."""
        rows = min(rows, len(data))
        today = date.today()
        max_rel = max(len(str(d.get("cycle") or d.get("releaseCycle"))) for d in data[:rows] + [{}])
        max_latest = max(len(str(d.get("latest", ""))) for d in data[:rows] + [{}])
        header = f"*{slug} — релизы*"
        line_top = f"┌{'─'*max_rel}┬{'─'*max_latest}┬───┬────────────┐"
        line_mid = f"├{'─'*max_rel}┼{'─'*max_latest}┼───┼────────────┤"
        line_bot = f"└{'─'*max_rel}┴{'─'*max_latest}┴───┴────────────┘"
        title = f"│ {'Релиз':<{max_rel}}│ {'Последний':<{max_latest}}│ Под│    EOL    │"

        body: list[str] = []
        hl = (highlight or "").lower()
        for rel in data[:rows]:
            cycle = str(rel.get("cycle") or rel.get("releaseCycle"))
            latest = str(rel.get("latest", "?"))
            sup = "Да" if self._supported(rel) else "Нет"
            eol = self._eol_desc(rel.get("eol"), today)
            mark = "▶" if hl and hl in {cycle.lower(), latest.lower()} else " "
            body.append(
                f"│{mark}{cycle:>{max_rel-1}}│ {latest:<{max_latest}}│ {sup:^3}│ {eol:<10}│"
            )

        return "\n".join([header, "```", line_top, title, line_mid, *body, line_bot, "```"])

    # ------------------------------------------------------------------ #
    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()
