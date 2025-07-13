import re
from typing import List, Tuple, Optional, Dict, Any
from rapidfuzz import process
from datetime import datetime
from aiogram.utils.chat_action import ChatActionMiddleware
from aiogram.utils.rate_limit import rate_limit
from tenacity import retry, stop_after_attempt, wait_exponential

# Константы для регулярных выражений
TOKEN_SPLIT_PATTERN = re.compile(r"[\n,;]+")
NAME_VERSION_PATTERN = re.compile(
    r"(?P<name>[A-Za-z0-9\-\s+.]+?)\s*(?:v|версия)?\s*(?P<version>[0-9]+(?:\.[0-9]+)*)",
    re.IGNORECASE
)
VERSION_PATTERN = re.compile(r"[0-9]+(?:\.[0-9]+)*")

# Добавьте новые паттерны
VERSION_PATTERNS = [
    re.compile(r"v?(\d+(?:\.\d+)*(-\w+)?)", re.IGNORECASE),  # v1.2.3, 1.2.3-beta
    re.compile(r"версия\s*(\d+(?:\.\d+)*)", re.IGNORECASE),  # версия 1.2.3
    re.compile(r"@(\d+(?:\.\d+)*)")  # python@3.8
]

def parse_tokens(text: str, slugs: List[str]) -> List[Tuple[str, str]]:
    """Разбивает строку на токены и извлекает имена и версии.

    Args:
        text (str): Входной текст для парсинга
        slugs (List[str]): Список известных slug-ов для сопоставления

    Returns:
        List[Tuple[str, str]]: Список кортежей (slug, version)

    Raises:
        ValueError: Если slugs пуст
    """
    if not slugs:
        raise ValueError("Список slugs не может быть пустым")

    tokens = TOKEN_SPLIT_PATTERN.split(text)
    results: List[Tuple[str, str]] = []

    for t in tokens:
        tok = t.strip()
        if not tok:
            continue

        # Попытка найти имя и версию через regex
        match = NAME_VERSION_PATTERN.search(tok)
        if match:
            name = match.group('name').strip().lower().replace(' ', '-')
            version = match.group('version')
        else:
            # Если regex не сработал, используем нечеткий поиск
            match_result = process.extractOne(tok, slugs)
            if not match_result:
                continue
            
            name_guess, score = match_result
            version_match = VERSION_PATTERN.search(tok)
            version = version_match.group() if version_match else ''
            name = name_guess

        results.append((name, version))

    return results

async def compute_info(name: str, version: str) -> str:
    try:
        data = await fetch_product(name)
        record = next((r for r in data if r['cycle'] == version), None)
        if not record:
            return L['not_found'].format(name=name, version=version)

        eol_date = datetime.fromisoformat(record['eol']).date()
        today = datetime.now(TZ).date()
        days = (eol_date - today).days

        # Добавляем информацию о поддержке
        support_info = []
        if 'support' in record:
            support_info.append(f"👨‍💻 Поддержка до: {record['support']}")
        if 'security' in record:
            support_info.append(f"🛡️ Безопасность до: {record['security']}")

        active = [r for r in data if datetime.fromisoformat(r['eol']).date() >= today]
        cycles = sorted([vparse(r['cycle']) for r in active])
        minv, maxv = cycles[0], cycles[-1]

        status = "✅ Поддерживается" if days > 0 else "❌ Не поддерживается"
        
        return "\n".join([
            f"📦 {name} {version}:",
            status,
            f"⏳ EOL через: {days} дней ({eol_date})",
            *support_info,
            f"📊 Актуальные версии: {minv} - {maxv}"
        ])
    except Exception as e:
        logger.error(f"Error in compute_info: {e}")
        return L['error'].format(error=str(e))

dp.middleware.setup(ChatActionMiddleware())

@rate_limit(5, 'default')  # 5 запросов в секунду
@dp.message()
async def on_message(msg: types.Message):
    # ...существующий код...

class Config:
    # ...существующий код...
    CACHE_KEY_PREFIX = "eol_bot:"
    CACHE_SETTINGS = {
        'default': {
            'cache': Cache.MEMORY,
            'serializer': JsonSerializer(),
            'ttl': 3600
        }
    }

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10)
)
async def fetch_product(slug: str) -> List[Dict[str, Any]]:
    # ...существующий код...