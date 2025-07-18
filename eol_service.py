import aiohttp, time, json, datetime as _dt, logging
from pathlib import Path
from typing import Any, List, Dict, Optional
from cache import TTLCache
from config import settings

log=logging.getLogger(__name__)
_cache = TTLCache()
_disk = Path("/tmp/eol_products_ru2.json")

class Eol:
    def __init__(self):
        self._sess: Optional[aiohttp.ClientSession]=None
        self._products: List[str]=[]
        self._prod_ts=0

    async def _session(self):
        if not self._sess:
            self._sess=aiohttp.ClientSession(raise_for_status=True, timeout=aiohttp.ClientTimeout(total=10))
        return self._sess

    async def _get_json(self, path:str):
        s=await self._session()
        url=f"{settings.API_ROOT.rstrip('/')}/{path.lstrip('/')}"
        async with s.get(url) as r:
            return await r.json()

    async def products(self)->List[str]:
        if self._products and time.time()-self._prod_ts < settings.PRODUCTS_TTL:
            return self._products
        try:
            data=await self._get_json("products.json")
            self._products=[d['slug'] if isinstance(d,dict) else d for d in data]
            self._prod_ts=time.time()
            _disk.write_text(json.dumps({"ts":self._prod_ts,"data":self._products}))
        except Exception as e:
            log.warning("products.json failed: %s",e)
            if _disk.exists():
                obj=json.loads(_disk.read_text())
                self._products=obj["data"]; self._prod_ts=obj["ts"]
        return self._products

    async def releases(self, slug:str)->Optional[List[Dict]]:
        cached=await _cache.get(slug, settings.RELEASE_TTL)
        if cached is not None:
            return cached
        for p in [f"v1/{slug}.json", f"{slug}.json"]:
            try:
                data=await self._get_json(p)
                await _cache.set(slug, data)
                return data
            except Exception:
                continue
        return None

    def _sup(self, rel)->bool:
        return str(rel.get('support') or rel.get('supported')).lower() in {"true","yes","active","supported"}

    def _eol(self, eol_raw, today)->str:
        if isinstance(eol_raw,str) and eol_raw:
            try:
                dt=_dt.date.fromisoformat(eol_raw)
                diff=(dt-today).days
                if diff<0: return "EOL"
                return f"EOL через {diff//365}г{(diff%365)//30}м"
            except ValueError:
                return f"EOL: {eol_raw}"
        return "дата EOL не указана"

    async def status_line(self, slug:str, version:Optional[str]):
        data=await self.releases(slug)
        if data is None: return f"❌ {slug}: не найдено"
        rel=None
        if version:
            v=version.lower()
            for r in data:
                if v in {str(r.get('cycle','')).lower(), str(r.get('latest','')).lower()}:
                    rel=r; break
        if rel is None: rel=data[0]
        cycle=rel.get('cycle') or rel.get('releaseCycle','?')
        latest=rel.get('latest','?')
        sup=self._sup(rel)
        sup_icon="✅" if sup else "❌"
        today=_dt.date.today()
        return f"{sup_icon} {slug} {cycle} → {latest} ({self._eol(rel.get('eol'), today)})"

    def fancy_table(self, slug:str, data:List[Dict], highlight:Optional[str]=None, rows:int=7)->str:
        # build widths
        rows=min(rows,len(data))
        rels=[str(d.get('cycle') or d.get('releaseCycle','')) for d in data[:rows]]
        latests=[str(d.get('latest','')) for d in data[:rows]]
        w_rel=max(6,max(len(r) for r in rels))
        w_latest=max(7,max(len(l) for l in latests))
        header=f"*{slug} — релизы*"
        top=f"┌{'─'*w_rel}┬{'─'*w_latest}┬───┬─────────────┐"
        mid=f"├{'─'*w_rel}┼{'─'*w_latest}┼───┼─────────────┤"
        bot=f"└{'─'*w_rel}┴{'─'*w_latest}┴───┴─────────────┘"
        title=f"│ {'Релиз':<{w_rel-1}}│ {'Последний':<{w_latest-1}}│ Под│     EOL     │"
        lines=[header,"```",top,title,mid]
        hl_low=highlight.lower() if highlight else ""
        today=_dt.date.today()
        for r in data[:rows]:
            rel=str(r.get('cycle') or r.get('releaseCycle',''))
            latest=str(r.get('latest',''))
            sup="Да" if self._sup(r) else "Нет"
            eol=self._eol(r.get('eol'), today)
            marker="▶" if hl_low and hl_low in {rel.lower(), latest.lower()} else " "
            line=f"│{marker}{rel:>{w_rel-1}}│ {latest:<{w_latest-1}}│ {sup:^3}│ {eol:<11} │"
            lines.append(line)
        lines.append(bot)
        lines.append("```")
        return "\n".join(lines)

    async def close(self):
        if self._sess and not self._sess.closed:
            await self._sess.close()
