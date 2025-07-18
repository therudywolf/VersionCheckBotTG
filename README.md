
# VersionBot 🇷🇺

**VersionBot** — Telegram‑бот, который помогает проверить срок поддержки (End‑of‑Life) популярных
программных продуктов c сайта [endoflife.date](https://endoflife.date).

## Возможности

* ❓ Быстро узнавайте, поддерживается ли версия ПО, просто написав её название и номер  
  `python 3.11`
* 📊 Красивые ASCII‑таблицы с деталями поддержки
* ✔️ Проверка сразу нескольких продуктов одним сообщением
* 📋 Поддержка маркированных списков и .txt‑файлов
* ⚡️ Инлайн‑режим — используйте `@VersionEOLBot nodejs` прямо в других чатах
* 🐳 Готов к запуску в Docker / Docker Compose

## Быстрый старт

```bash
git clone https://github.com/therudywolf/versionbot.git
cd versionbot
cp .env.example .env        # установите BOT_TOKEN
docker compose up -d        # или python -m versionbot.bot
```

Боту нужен **токен Telegram‑бота** (`BOT_TOKEN`). Получите его у @BotFather и пропишите
в .env или переменной окружения.

## Команды

| Команда | Описание |
|---------|----------|
| `/start` | Краткая справка |
| `/help`  | Полная документация |
| `@BotName запрос` | Инлайн‑режим |

## Конфигурация

Все настройки задаются переменными окружения:

| Переменная | Значение по умолчанию | Описание |
|------------|----------------------|----------|
| `BOT_TOKEN` |  — | Токен Telegram‑бота |
| `EOL_API_ROOT` | https://endoflife.date/api | Базовый URL API |
| `RELEASE_TTL` | 21600 | Cache TTL релизов (сек) |
| `PRODUCTS_TTL` | 86400 | Cache TTL списка продуктов (сек) |
| `MAX_PARALLEL` | 15 | Максимум параллельных запросов к API |

## Лицензия

MIT. Автор: [therudywolf](https://github.com/therudywolf)
