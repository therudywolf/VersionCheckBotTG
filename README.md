# Telegram EOL Bot (v2)

Telegram‑бот для быстрой проверки, поддерживается ли версия ПО,
использует публичный API `endoflife.date`.

## Изменения
* Исправлен базовый URL API (`https://endoflife.date/api/<slug>.json`).
* Обновлены инструкции и Docker Compose.

## Запуск

```bash
cp .env.example .env  # укажите BOT_TOKEN
docker compose up --build -d
```

## Использование
```
nodejs 22, nginx, go1.22
```
Или inline: `@your_bot python 3.13`.
