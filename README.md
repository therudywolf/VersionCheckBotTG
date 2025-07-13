# Telegram EOL Bot

Бот для проверки сроков поддержки ПО через API https://endoflife.date/ с:
- Inline режимом
- Кешированием (aiocache)
- Расширенным парсером названий и версий
- Локализацией (рус.)

## Установка

```bash
git clone https://github.com/your/repo.git
cd telegram_eol_bot
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Конфигурация

Создайте файл `.env` рядом с `main.py`:
```
BOT_TOKEN=ваш_токен
```

## Запуск

```bash
python main.py
```

## Docker

```bash
docker build -t telegram-eol-bot .
docker run -d --env BOT_TOKEN=ваш_токен telegram-eol-bot
```