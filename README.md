# VersionBot – Telegram inline‑бот для проверки EOL/поддержки версий

Данные берутся из публичного API **https://endoflife.date/api/v1**.

## Запуск

```bash
git clone … && cd versionbot
cp .env.example .env   # BOT_TOKEN=...
docker compose up --build -d
```

## Возможности
* Распознаёт списки с версиями (`nodejs 22`, `go1.22`) в любом формате.
* Inline‑режим c fuzzy‑поиском slug’ов (`@botname pythn 3.12`).
* Кэширует `products.json` на диск + LRU для release‑JSON.
* `/reload` — принудительно обновить кэш списка продуктов.

MIT License.
