import aiohttp, logging, time, datetime as _dt, json, asyncio
from pathlib import Path
from typing import Any, List, Optional, Dict
from cache import TTLCache
from config import settings

log = logging.getLogger(__name__)
_prod_disk = Path("/tmp/eol_products.json")
_cache = TTLCache()

class EolService:
    def __init__(self):
        self._session: Optional[aiohttp.ClientSession] = None
        self._products_ts = 0
        self._products: List[str] = []

    async def _ensure_session(self):
        if not self._session:
            self._session = aiohttp.ClientSession(raise_for_status=True, timeout=aiohttp.ClientTimeout(total=8))

    async def _get_json(self, path: str):
        await self._ensure_session()
        url = f"{settings.API_ROOT.rstrip('/')}/{path.lstrip('/')}"
        async with self._session.get(url) as resp:
            return await resp.json()

    async def products(self) -> List[str]:
        if self._products and time.time() - self._products_ts < settings.PRODUCTS_TTL:
            return self._products
        try:
            data = await self._get_json("products.json")
            self._products = [d["slug"] if isinstance(d, dict) else d for d in data]
            self._products_ts = time.time()
            _prod_disk.write_text(json.dumps({"ts": self._products_ts, "data": self._products}))
        except Exception as e:
            log.warning("products.json fetch failed: %s", e)
            if _prod_disk.exists():
                cached = json.loads(_prod_disk.read_text())
                self._products = cached["data"]
                self._products_ts = cached["ts"]
        return self._products

    async def release_data(self, slug: str) -> Optional[List[Dict]]:
        # cache per slug
        cached = await _cache.get(slug, settings.RELEASE_TTL)
        if cached is not None:
            return cached
        paths = [f"v1/{slug}.json", f"{slug}.json"]
        for p in paths:
            try:
                data = await self._get_json(p)
                await _cache.set(slug, data)
                return data
            except Exception:
                continue
        return None

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    async def status_line(self, slug: str, version: Optional[str]) -> str:
        data = await self.release_data(slug)
        if data is None:
            return f"❌ {slug}: не найдено"
        today = _dt.date.today()

        rel = None
        if version:
            v = version.lower()
            for r in data:
                if v in {str(r.get('cycle','')).lower(), str(r.get('latest','')).lower()}:
                    rel = r; break
        if rel is None:
            rel = data[0]

        cycle = rel.get('cycle') or rel.get('releaseCycle', 'n/a')
        latest = rel.get('latest', 'n/a')
        sup = str(rel.get('support') or rel.get('supported')).lower() in {"true","yes","active","supported"}
        sup_flag = "✅" if sup else "❌"
        eol = rel.get('eol')
        eol_desc = self._eol_desc(eol, today)
        return f"{sup_flag} {slug} {cycle} → {latest} ({eol_desc})"

    def _eol_desc(self, eol, today):
        if isinstance(eol, str) and eol:
            try:
                dt = _dt.date.fromisoformat(eol)
                delta = (dt - today).days
                if delta < 0:
                    return "EOL"
                return f"EOL через {delta//365}y{(delta%365)//30}m"
            except ValueError:
                return f"EOL: {eol}"
        return "дата EOL не указана"

    def make_table(self, slug: str, data: List[Dict], rows: int = 5) -> str:
        header = f"*{slug} — релизы*\n`Release | Latest | Support | EOL`\n`------ | ------ | ------- | ---`\n"
        lines = []
        for r in data[:rows]:
            rel = str(r.get('cycle') or r.get('releaseCycle', '?'))
            latest = str(r.get('latest', '?'))
            sup = "Yes" if str(r.get('support') or r.get('supported')).lower() in {"true","yes","active","supported"} else "No"
            eol = r.get('eol') or "—"
            lines.append(f"`{rel:<6}| {latest:<6}| {sup:<7}| {eol}`")
        return header + "\n".join(lines)
