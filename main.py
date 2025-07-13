import os
import json
import asyncio
from datetime import datetime
import pytz
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineQueryResultArticle, InputTextMessageContent
import httpx
from packaging.version import parse as vparse
from aiocache import cached, Cache
from aiocache.serializers import JsonSerializer
from dotenv import load_dotenv
from utils.parser import parse_tokens

# Загрузка .env
load_dotenv()
BOT_TOKEN = os.getenv('BOT_TOKEN')
API_BASE = 'https://endoflife.date/api/v1'
TZ = pytz.timezone('Europe/Berlin')

# Локализация
with open('locales/ru.json', encoding='utf-8') as f:
    L = json.load(f)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

# Кеш: список продуктов обновляется каждые 12ч
@cached(ttl=12*3600, cache=Cache.MEMORY, serializer=JsonSerializer())
async def get_slugs():
    async with httpx.AsyncClient() as client:
        data = await client.get(f"{API_BASE}/products.json")
    items = data.json()
    return [it['slug'] for it in items]

# Кеш для запросов продуктов (1ч)
@cached(ttl=3600, cache=Cache.MEMORY, serializer=JsonSerializer())
async def fetch_product(slug: str):
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{API_BASE}/products/{slug}.json")
    return r.json()

async def compute_info(name: str, version: str) -> str:
    data = await fetch_product(name)
    # поиск EOL для версии
    record = next((r for r in data if r['cycle'] == version), None)
    if not record:
        return L['not_found'].format(name=name, version=version)
    eol_date = datetime.fromisoformat(record['eol']).date()
    today = datetime.now(TZ).date()
    days = (eol_date - today).days
    # активные
    active = [r for r in data if datetime.fromisoformat(r['eol']).date() >= today]
    cycles = sorted([vparse(r['cycle']) for r in active])
    minv, maxv = cycles[0], cycles[-1]
    return L['eol_info'].format(name=name, version=version,
                                 eol=eol_date.isoformat(), days=days,
                                 minv=minv, maxv=maxv)

@dp.message(commands=['start', 'help'])
async def cmd_start(msg: types.Message):
    await msg.answer(L['start'].format(bot=(await bot.get_me()).username))

@dp.message()
async def on_message(msg: types.Message):
    slugs = await get_slugs()
    parsed = parse_tokens(msg.text, slugs)
    resp = []
    for name, ver in parsed:
        resp.append(await compute_info(name, ver))
    await msg.answer("\n".join(resp))

@dp.inline_query()
async def on_inline(query: types.InlineQuery):
    slugs = await get_slugs()
    parsed = parse_tokens(query.query, slugs)
    results = []
    for idx, (name, ver) in enumerate(parsed):
        text = await compute_info(name, ver)
        results.append(
            InlineQueryResultArticle(
                id=str(idx),
                title=f"{name} {ver}",
                input_message_content=InputTextMessageContent(text)
            )
        )
    await query.answer(results, cache_time=300)

if __name__ == '__main__':
    asyncio.run(dp.start_polling())