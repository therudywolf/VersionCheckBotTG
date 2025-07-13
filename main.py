import os
import json
import asyncio
from datetime import datetime
from typing import List, Dict, Any, Optional
import pytz
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineQueryResultArticle, InputTextMessageContent
import httpx
from packaging.version import parse as vparse, Version
from aiocache import cached, Cache
from aiocache.serializers import JsonSerializer
from dotenv import load_dotenv
from utils.parser import parse_tokens
from rapidfuzz import process
import logging

# Конфигурация
class Config:
    BOT_TOKEN: str
    API_BASE: str = 'https://endoflife.date/api/v1'
    TIMEZONE: str = 'Europe/Berlin'
    CACHE_TTL_PRODUCTS: int = 12 * 3600  # 12 часов
    CACHE_TTL_SLUGS: int = 3600  # 1 час
    LOCALE_PATH: str = 'locales/ru.json'

    @classmethod
    def load(cls) -> None:
        load_dotenv()
        cls.BOT_TOKEN = os.getenv('BOT_TOKEN')
        if not cls.BOT_TOKEN:
            raise ValueError("BOT_TOKEN не найден в переменных окружения")

# Инициализация конфигурации
Config.load()
TZ = pytz.timezone(Config.TIMEZONE)

# Загрузка локализации
try:
    with open(Config.LOCALE_PATH, encoding='utf-8') as f:
        L = json.load(f)
except (FileNotFoundError, json.JSONDecodeError) as e:
    raise RuntimeError(f"Ошибка загрузки локализации: {e}")

bot = Bot(token=Config.BOT_TOKEN)
dp = Dispatcher(bot)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='bot.log'
)
logger = logging.getLogger(__name__)

@cached(ttl=Config.CACHE_TTL_PRODUCTS, cache=Cache.MEMORY, serializer=JsonSerializer())
async def get_slugs() -> List[str]:
    """Получает список всех доступных продуктов."""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{Config.API_BASE}/products.json")
            response.raise_for_status()
            items = response.json()
            return [it['slug'] for it in items]
        except (httpx.HTTPError, json.JSONDecodeError) as e:
            logger.error(f"Ошибка получения списка продуктов: {e}")
            raise RuntimeError(f"Ошибка получения списка продуктов: {e}")

@cached(ttl=Config.CACHE_TTL_SLUGS, cache=Cache.MEMORY, serializer=JsonSerializer())
async def fetch_product(slug: str) -> List[Dict[str, Any]]:
    """Получает информацию о конкретном продукте."""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{Config.API_BASE}/products/{slug}.json")
            response.raise_for_status()
            return response.json()
        except (httpx.HTTPError, json.JSONDecodeError) as e:
            logger.error(f"Ошибка получения информации о продукте {slug}: {e}")
            raise RuntimeError(f"Ошибка получения информации о продукте {slug}: {e}")

async def compute_info(name: str, version: Optional[str]) -> str:
    """
    Вычисляет информацию о EOL для указанной версии продукта.
    Если версия не указана, берёт самую свежую поддерживаемую.
    """
    try:
        data = await fetch_product(name)
        today = datetime.now(TZ).date()
        # Если версия не указана, берём самую свежую поддерживаемую
        if not version:
            active = [r for r in data if datetime.fromisoformat(r['eol']).date() >= today]
            if not active:
                return f"❌ Не найдено актуальных версий для {name}"
            latest = max(active, key=lambda r: vparse(r['cycle']))
            version = latest['cycle']
            record = latest
        else:
            record = next((r for r in data if r['cycle'] == version), None)
            if not record:
                # Если версия не найдена, показать доступные версии
                available = ', '.join(r['cycle'] for r in data)
                return f"❌ Версия {version} для {name} не найдена.\nДоступные: {available}"
        eol_date = datetime.fromisoformat(record['eol']).date()
        days = (eol_date - today).days
        status = "✅ Поддерживается" if days > 0 else "❌ Не поддерживается"
        # Ссылку на продукт
        url = f"https://endoflife.date/{name}"
        # Актуальные версии
        active = [r for r in data if datetime.fromisoformat(r['eol']).date() >= today]
        cycles = sorted([vparse(r['cycle']) for r in active]) if active else []
        minv, maxv = (cycles[0], cycles[-1]) if cycles else (None, None)
        # Информация о поддержке
        support_info = []
        if 'support' in record and record['support']:
            support_info.append(f"👨‍💻 Поддержка до: {record['support']}")
        if 'security' in record and record['security']:
            support_info.append(f"🛡️ Безопасность до: {record['security']}")
        return "\n".join([
            f"📦 [{name} {version}]({url}):",
            status,
            f"⏳ EOL через: {days} дней ({eol_date})",
            *support_info,
            f"📊 Актуальные версии: {minv} - {maxv}" if minv and maxv else "",
        ])
    except Exception as e:
        logger.error(f"Ошибка в compute_info: {e}")
        return L['error'].format(error=str(e))

@dp.message(commands=['start', 'help'])
async def cmd_start(msg: types.Message):
    """Приветствие и помощь."""
    await msg.answer(L['start'].format(bot=(await bot.get_me()).username), disable_web_page_preview=True)

@dp.message(commands=['about'])
async def cmd_about(msg: types.Message):
    """Информация о боте."""
    await msg.answer(
        "🤖 Бот для проверки сроков поддержки ПО через https://endoflife.date/\n"
        "Исходники: https://github.com/endoflife-date/endoflife\n"
        "Примеры: python 3.10, nodejs@18, php v8.2, ubuntu 22.04",
        disable_web_page_preview=True
    )

@dp.message(commands=['latest'])
async def cmd_latest(msg: types.Message):
    """Показывает последние версии популярных продуктов."""
    popular = ['python', 'php', 'nodejs', 'ubuntu']
    results = []
    for product in popular:
        data = await fetch_product(product)
        latest = max([vparse(r['cycle']) for r in data])
        results.append(f"{product}: {latest}")
    await msg.answer("\n".join(results))

@dp.message(commands=['search'])
async def cmd_search(msg: types.Message):
    """Поиск по доступным продуктам."""
    query = msg.text.replace('/search', '').strip()
    if not query:
        await msg.answer("Укажите запрос после /search")
        return
    slugs = await get_slugs()
    matches = process.extract(query, slugs, limit=5)
    if matches:
        result = "Найдено:\n" + "\n".join(f"• {m[0]}" for m in matches)
    else:
        result = "Ничего не найдено"
    await msg.answer(result)

@dp.message()
async def on_message(msg: types.Message):
    """Обработка обычных сообщений."""
    if not msg.text or not msg.text.strip():
        await msg.answer("Пожалуйста, отправьте название продукта и версию.")
        return
    slugs = await get_slugs()
    parsed = parse_tokens(msg.text, slugs)
    if not parsed:
        # Попробовать подсказать похожие продукты
        matches = process.extract(msg.text, slugs, limit=3)
        if matches:
            hint = "Возможно, вы имели в виду:\n" + "\n".join(f"• {m[0]}" for m in matches)
        else:
            hint = "Не удалось распознать продукт."
        await msg.answer(hint)
        return
    resp = []
    for name, ver in parsed:
        resp.append(await compute_info(name, ver))
    await msg.answer("\n\n".join(resp), disable_web_page_preview=True)

@dp.inline_query()
async def on_inline(query: types.InlineQuery):
    """Инлайн-режим."""
    slugs = await get_slugs()
    parsed = parse_tokens(query.query, slugs)
    results = []
    for idx, (name, ver) in enumerate(parsed):
        text = await compute_info(name, ver)
        results.append(
            InlineQueryResultArticle(
                id=str(idx),
                title=f"{name} {ver}",
                input_message_content=InputTextMessageContent(text, disable_web_page_preview=True)
            )
        )
    await query.answer(results, cache_time=300)

if __name__ == '__main__':
    asyncio.run(dp.start_polling())