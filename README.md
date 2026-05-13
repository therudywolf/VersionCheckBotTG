# 🐺 VersionCheckBot

> `D34D1N$1D3` :: numb but alive :: version, EOL, and CVE monitoring bot

My resources:
- [Gravatar](https://gravatar.com/therudywolf)
- [OneToThree](https://onetothree.ru)
- [Forest blog](https://t.me/theforestserver)
- [X](https://x.com/therudywolf)
- [GitHub](https://github.com/therudywolf)
- [Twitch](https://twitch.tv/therudywolf)
- [Reddit](https://reddit.com/user/Most-Watercress-6718)
- [Telegram](https://t.me/rudy_wolf)
- [YouTube](https://youtube.com/channel/UCXHkoSlaY5QaNmN_l4t0djQ)

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![License: AGPL-3.0](https://img.shields.io/badge/license-AGPL--3.0-blue.svg)](LICENSE)
[![Telegram Bot API](https://img.shields.io/badge/Telegram%20Bot%20API-21.x-26A5E4?logo=telegram&logoColor=white)](https://core.telegram.org/bots/api)
[![endoflife.date](https://img.shields.io/badge/data-endoflife.date-orange)](https://endoflife.date)

Telegram-бот для мониторинга версий ПО, проверки End-of-Life статуса и отслеживания CVE-уязвимостей.
Данные берутся из бесплатного API [endoflife.date](https://endoflife.date) (450+ продуктов) и [NVD](https://nvd.nist.gov/) (CVE).

AGPL v3 Copyleft applies to reuse, modification, and network deployment of derived versions.

> **[English version below](#english)**

---

## Возможности

- **Проверка версий** — статус поддержки, дата EOL, последний релиз
- **Подписки и мониторинг** — автоматические уведомления при смене статуса
- **CVE-интеграция** — поиск уязвимостей через NVD API
- **Inline-режим** — быстрая проверка прямо из любого чата
- **Умный поиск** — fuzzy matching + алиасы (`node` -> `nodejs`, `k8s` -> `kubernetes`)
- **Обработка файлов** — отправьте `.txt` со списком продуктов
- **Экспорт/импорт** — подписки в JSON и CSV
- **Избранное, история, уведомления** — персональные настройки
- **Администрирование** — режимы доступа, рассылки, статистика, backup

## Быстрый старт

### 1. Клонирование и установка

```bash
git clone https://github.com/therudywolf/VersionCheckBotTG.git
cd VersionCheckBotTG
pip install -r requirements.txt
```

### 2. Настройка

```bash
cp .env.example .env
```

Откройте `.env` и укажите `BOT_TOKEN` (получить у [@BotFather](https://t.me/BotFather)):

```env
BOT_TOKEN=<telegram_bot_token>
```

### 3. Запуск

```bash
python bot.py
```

Или через Docker:

```bash
docker compose up -d
```

### 4. Проверка

Отправьте боту:

```
python 3.11
```

## Команды

| Команда | Описание |
|---------|----------|
| `/start` | Начать работу |
| `/help` | Справка по командам |
| `/check <продукт> [версия]` | Проверить статус версии |
| `/subscribe <продукт> [версия]` | Подписаться на мониторинг |
| `/subscriptions` | Список подписок |
| `/cve <продукт> [версия]` | Поиск CVE |
| `/compare <п1> <в1> <п2> <в2>` | Сравнение версий |
| `/favorites [add\|remove] <п>` | Избранные продукты |
| `/alerts` | Настройки уведомлений |
| `/history` | История запросов |
| `/export [json\|csv]` | Экспорт подписок |
| `/import` | Импорт подписок из файла |
| `/health` | Состояние бота |
| `/stats` | Статистика (админ) |
| `/admin` | Административные команды (админ) |

**Inline-режим:** `@имя_бота python 3.11` в любом чате.

**Несколько продуктов сразу:** `python 3.11, nodejs 22, java 17`

## Конфигурация

Все параметры задаются через переменные окружения (`.env`).

| Переменная | По умолчанию | Описание |
|------------|-------------|----------|
| `BOT_TOKEN` | — | **Обязательно.** Токен от @BotFather |
| `ADMIN_IDS` | — | Telegram ID администраторов (через запятую) |
| `NVD_API_KEY` | — | API-ключ NVD для CVE ([получить](https://nvd.nist.gov/developers/request-an-api-key)) |
| `DATABASE_URL` | `sqlite:///./bot.db` | SQLite или PostgreSQL |
| `RELEASE_TTL` | `21600` | Кэш релизов (сек) |
| `PRODUCTS_TTL` | `86400` | Кэш списка продуктов (сек) |
| `CVE_TTL` | `43200` | Кэш CVE (сек) |
| `MAX_PARALLEL` | `15` | Макс. параллельных запросов |
| `RATE_LIMIT_PER_MINUTE` | `20` | Лимит запросов/мин на пользователя |
| `RATE_LIMIT_PER_HOUR` | `200` | Лимит запросов/час на пользователя |
| `SCHEDULER_INTERVAL` | `21600` | Интервал проверки подписок (сек) |
| `NOTIFICATION_ENABLED` | `true` | Включить уведомления |
| `LOG_LEVEL` | `INFO` | Уровень логирования |

Полный пример — в [`.env.example`](.env.example).

## Архитектура

```
VersionCheckBotTG/
├── bot.py                  # Точка входа
├── config.py               # Конфигурация (dataclass + валидация)
├── bot/
│   ├── handlers/           # Telegram-обработчики
│   │   ├── commands.py     #   команды (/check, /subscribe, /admin, ...)
│   │   ├── callbacks.py    #   inline-кнопки
│   │   ├── inline.py       #   inline-режим
│   │   └── messages.py     #   текст и файлы
│   ├── services/           # Бизнес-логика
│   │   ├── version_service.py      # endoflife.date API
│   │   ├── cve_service.py          # NVD API
│   │   ├── monitoring_service.py   # Подписки
│   │   └── notification_service.py # Уведомления
│   ├── models/             # SQLAlchemy-модели
│   ├── database/           # Engine + Session
│   ├── scheduler/          # Фоновые задачи
│   └── utils/              # Кэш, парсер, fuzzy, rate limiter, retry, ...
├── alembic/                # Миграции БД
├── tests/                  # Тесты (pytest)
├── scripts/                # Утилиты (миграции, backup)
├── Dockerfile
├── docker-compose.yml
└── docker-compose.dev.yml
```

### Слои

```
 Telegram (handlers)
        │
 Services (version, cve, monitoring, notification)
        │
 Data (SQLAlchemy models, TTLCache, aiohttp → endoflife.date / NVD)
        │
 Scheduler (background subscription & CVE checks)
```

### Ключевые паттерны

- **Singleton** — `VersionService.shared()` предотвращает утечки aiohttp-сессий
- **Circuit Breaker** — защита от каскадных сбоев при недоступности API
- **Token Bucket / Sliding Window** — rate limiting для API и пользователей
- **Retry с exponential backoff** — автоматические повторы при ошибках
- **TTL Cache с disk persistence** — быстрый доступ + переживание рестартов
- **Decorator stack** — `@error_handler` > `@access_required` > `@rate_limit_handler`

## Docker

### Production

```bash
docker compose up -d
```

### Development (с PostgreSQL)

```bash
docker compose -f docker-compose.dev.yml up -d
```

В dev-режиме исходники монтируются в контейнер, логирование установлено в `DEBUG`.

## Тестирование

```bash
pytest
```

С покрытием:

```bash
pytest --cov=bot --cov-report=html
```

## Безопасность и FOSS hygiene

- Не коммитьте `.env`, логи, кэш, SQLite-базы, backup-файлы, IDE-state и `__pycache__`.
- Реальные токены и пароли храните только в `.env` или secret store деплоя.
- Если токен Telegram/NVD или пароль попал в историю git, перевыпустите его у провайдера.
- Перед публикацией проверяйте `git status --ignored` и `git diff --cached`.

Подробности см. в [SECURITY.md](SECURITY.md).

## Участие в проекте

Приветствуются любые вклады! См. [CONTRIBUTING.md](CONTRIBUTING.md) и [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

1. Fork репозитория
2. Создайте ветку (`git checkout -b feature/my-feature`)
3. Закоммитьте (`git commit -m 'feat: add my feature'`)
4. Push (`git push origin feature/my-feature`)
5. Откройте Pull Request

## Лицензия

[GNU Affero General Public License v3.0](LICENSE) &copy; 2024-2026 VersionCheckBot contributors

---

<a id="english"></a>

## English

**VersionCheckBot** is a Telegram bot that monitors software versions, checks End-of-Life status, and tracks CVE vulnerabilities. It uses the free [endoflife.date](https://endoflife.date) API (450+ products) and [NVD](https://nvd.nist.gov/) for CVE data.

### Features

- Version status checks with EOL dates and latest releases
- Subscriptions with automatic status change notifications
- CVE search and monitoring via NVD API
- Inline mode for quick lookups from any chat
- Fuzzy product name matching with alias support
- File processing (`.txt` lists), export/import (JSON/CSV)
- Favorites, query history, notification preferences
- Admin panel: access modes, broadcasts, stats, database backup

### Quick Start

```bash
git clone https://github.com/therudywolf/VersionCheckBotTG.git
cd VersionCheckBotTG
cp .env.example .env       # set BOT_TOKEN
pip install -r requirements.txt
python bot.py
```

Or with Docker:

```bash
docker compose up -d
```

### Configuration

All settings are environment variables. See [`.env.example`](.env.example) for the full list. Only `BOT_TOKEN` is required.

### Security and FOSS Hygiene

Do not commit `.env`, logs, cache files, SQLite databases, backups, IDE state, or
Python bytecode. Keep real tokens and passwords in `.env` or in your deployment
secret store. If a secret reaches git history, rotate it at the provider.

See [SECURITY.md](SECURITY.md) for details.

### License

[GNU Affero General Public License v3.0](LICENSE)
