# VersionBot — Telegram‑бот проверки поддерживаемости версий

Проверьте, поддерживается ли ваш `python 3.11`, `nginx`, `nodejs 20` и ещё 380+ продуктов — бот берёт данные напрямую из публичного API **endoflife.date**.

## Возможности

* **Кривой ввод OK** — через запятые, пробелы, переносы, `go1.22`.
* **Inline‑режим:** `@version_bot nodejs 22` — показывает карточку прямо в любом чате.
* **Fuzzy‑поиск** slugs (RapidFuzz / difflib) — найдёт `nodje`, подскажет близкие совпадения.
* **Кэш** перечня продуктов (24 ч) и отдельных JSON (LRU 512 шт.) — экономит API.
* **/reload** — принудительно обновить список продуктов.
* **Docker Compose** one‑liner деплой.

## Запуск

```bash
git clone …/versionbot.git && cd versionbot
cp .env.example .env   # вставьте BOT_TOKEN
docker compose up --build -d
```

## Переменные окружения

| VAR            | По умолчанию | Описание                          |
|----------------|--------------|-----------------------------------|
| `BOT_TOKEN`    | —            | Токен вашего Telegram‑бота        |
| `CACHE_TTL`    | 21600        | TTL кэша release‑JSON (сек)       |
| `EOL_API_BASE` | https://…    | URL API endoflife.date           |
| `DEBUG`        | 0            | Расширенный лог (1/0)             |

## Архитектура

```
bot.py           # точка входа, Telegram‑хэндлеры
eol_service.py   # кэш + HTTP‑клиент EoL API
parser.py        # разбор пользовательского ввода
fuzzy.py         # RapidFuzz/difflib обёртка
config.py        # dataclass Settings
```

## Лицензия
MIT
