import datetime as _dt
from typing import Optional
import aiohttp

# Production API base path
API_BASE = "https://endoflife.date/api"

async def _get_json(url: str):
    async with aiohttp.ClientSession() as session:
        async with session.get(url, timeout=10) as resp:
            resp.raise_for_status()
            return await resp.json()

async def fetch_product_data(product: str):
    # slug must match canonical URL (nodejs, nginx, python, ...).
    return await _get_json(f"{API_BASE}/{product}.json")

async def fetch_version_status(product: str, version: Optional[str]) -> str:
    try:
        data = await fetch_product_data(product)
    except Exception as exc:
        return f"❌ {product}: ошибка запроса — {exc}"

    today = _dt.date.today()
    release = None
    if version:
        for rel in data:
            cycle = str(rel.get('cycle') or rel.get('releaseCycle', '')).lower()
            latest = str(rel.get('latest', '')).lower()
            if version.lower() in (cycle, latest):
                release = rel
                break
    if release is None:
        release = data[0]

    cycle = release.get('cycle') or release.get('releaseCycle', 'n/a')
    latest = release.get('latest', 'n/a')
    eol = release.get('eol', 'n/a')

    status = []
    if eol != 'n/a':
        try:
            eol_dt = _dt.date.fromisoformat(eol)
            if eol_dt < today:
                status.append("EOL")
            else:
                days = (eol_dt - today).days
                status.append(f"EOL через {days // 365}y{(days % 365)//30}m")
        except ValueError:
            status.append(f"EOL: {eol}")

    support = str(release.get('support') or release.get('supported')).lower()
    status.insert(0, "поддерживается" if support in ("true", "yes", "active", "supported") else "не поддерживается")

    return f"🔹 {product} {cycle} → {latest} ({', '.join(status)})"
