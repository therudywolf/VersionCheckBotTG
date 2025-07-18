import aiohttp, time, logging, json, datetime as _dt
from pathlib import Path
from typing import Any, Dict, List, Optional
from cache import TTLCache
from config import settings

log = logging.getLogger(__name__)
_cache = TTLCache()
_disk = Path("/tmp/eol_products_cache_ru.json")

class Eol:
    def __init__(self):
        self._sess: Optional[aiohttp.ClientSession] = None
        self._products: List[str] = []
        self._prod_ts = 0

    async def _session(self):
        if not self._sess:
            self._sess = aiohttp.ClientSession(raise_for_status=True, timeout=aiohttp.ClientTimeout(total=8))
        return self._sess

    async def _fetch_json(self, path:str):
        sess = await self._session()
        url = f"{settings.API_ROOT.rstrip('/')}/{path.lstrip('/')}"
        async with sess.get(url) as r:
            return await r.json()

    async def products(self)->List[str]:
        if self._products and time.time()-self._prod_ts<settings.PRODUCTS_TTL:
            return self._products
        try:
            data = await self._fetch_json("products.json")
            self._products = [d["slug"] if isinstance(d, dict) else d for d in data]
            self._prod_ts=time.time()
            _disk.write_text(json.dumps({"ts":self._prod_ts,"data":self._products}))
        except Exception as e:
            log.warning("products.json fail: %s", e)
            if _disk.exists():
                tmp=json.loads(_disk.read_text())
                self._products=tmp["data"]; self._prod_ts=tmp["ts"]
        return self._products

    async def releases(self, slug:str)->Optional[List[Dict]]:
        cached=await _cache.get(slug, settings.RELEASE_TTL)
        if cached is not None:
            return cached
        for variant in [f"v1/{slug}.json", f"{slug}.json"]:
            try:
                data=await self._fetch_json(variant)
                await _cache.set(slug, data)
                return data
            except Exception:
                continue
        return None

    async def close(self):
        if self._sess and not self._sess.closed:
            await self._sess.close()

    # helpers
    def _eol_ru(self, eol_raw, today):
        if isinstance(eol_raw,str) and eol_raw:
            try:
                dt=_dt.date.fromisoformat(eol_raw)
                diff=(dt-today).days
                if diff<0: return "EOL"
                years=diff//365; months=(diff%365)//30
                return f"EOL через {years}г{months}м"
            except ValueError:
                return f"EOL: {eol_raw}"
        return "дата EOL не указана"

    def _sup_ru(self, rel):
        return str(rel.get('support') or rel.get('supported')).lower() in {"true","yes","active","supported"}

    async def status_line(self, slug:str, version:Optional[str]):
        data=await self.releases(slug)
        if data is None:
            return f"❌ {slug}: не найдено"
        rel=None
        if version:
            v=version.lower()
            for r in data:
                if v in {str(r.get('cycle','')).lower(), str(r.get('latest','')).lower()}:
                    rel=r;break
        if rel is None:
            rel=data[0]
        cycle = rel.get('cycle') or rel.get('releaseCycle', 'n/a')
        latest= rel.get('latest','n/a')
        eol_desc=self._eol_ru(rel.get('eol'), _dt.date.today())
        sup_flag="✅" if self._sup_ru(rel) else "❌"
        return f"{sup_flag} {slug} {cycle} → {latest} ({eol_desc})"


    def table(self, slug: str, data, highlight_version: str | None = None, rows: int = 8) -> str:
        """Return a nicely formatted ASCII table for Telegram Markdown messages."""
        from tabulate import tabulate

        hlver = highlight_version.lower() if highlight_version else ""
        rows_data = []
        for r in data[:rows]:
            rel    = str(r.get('cycle') or r.get('releaseCycle', '?'))
            latest = str(r.get('latest', '?'))
            sup    = "Да" if self._sup_ru(r) else "Нет"
            eol    = r.get('eol') or "—"
            marker = "▶ " if hlver and hlver in {rel.lower(), latest.lower()} else ""
            rows_data.append([marker + rel, latest, sup, eol])
        table_txt = tabulate(rows_data,
                             headers=["Версия", "Последняя", "Поддержка", "EOL"],
                             tablefmt="simple_grid",
                             stralign="left")
        return f"```\n{slug.upper()}\n{table_txt}\n```"


# === Improved table function ===

def table(self, slug:str, data, highlight_version:str|None=None, rows:int=8)->str:
    """Return a nicely formatted ASCII table for Telegram Markdown messages."""
    from tabulate import tabulate

    hlver = highlight_version.lower() if highlight_version else ""
    rows_data=[]
    for r in data[:rows]:
        rel     = str(r.get('cycle') or r.get('releaseCycle','?'))
        latest  = str(r.get('latest','?'))
        sup     = "Да" if self._sup_ru(r) else "Нет"
        eol     = r.get('eol') or "—"
        marker  = "▶ " if hlver and hlver in {rel.lower(), latest.lower()} else ""
        rows_data.append([marker+rel, latest, sup, eol])
    table_txt = tabulate(rows_data,
                         headers=["Версия","Последняя","Поддержка","EOL"],
                         tablefmt="simple_grid",
                         stralign="left")
    return f"```\n{slug.upper()}\n{table_txt}\n```"
