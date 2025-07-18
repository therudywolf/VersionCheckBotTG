import os
import logging
from telegram import Update, InlineQueryResultArticle, InputTextMessageContent
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    InlineQueryHandler,
    ContextTypes,
    filters,
)

from input_parser import parse_items
from eol_api import fetch_version_status

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Я проверяю актуальность версий ПО. "
        "Отправь список программ с версиями (или без) — "
        "через запятую, пробел, с новой строки либо файлом .txt.\n"
        "Пример: nodejs 22, python, go1.22"
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "/check <список> — проверить версии\n"
        "Можно прислать .txt‑файл.\n"
        "Inline режим: @<botname> nodejs 20"
    )

async def check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await handle_text(update, context, update.message.text or "")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    items = parse_items(text)
    if not items:
        await update.message.reply_text("Не удалось распознать продукты во входных данных.")
        return
    results = [await fetch_version_status(p, v) for p, v in items]
    await update.message.reply_text("\n".join(results))

async def check_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await handle_text(update, context, update.message.text or "")

async def check_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    if doc.mime_type != "text/plain":
        await update.message.reply_text("Пока читаю только текстовые .txt файлы.")
        return
    file = await doc.get_file()
    content = await file.download_as_bytes()
    await handle_text(update, context, content.decode("utf-8", errors="ignore"))

async def inline_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.inline_query.query
    items = parse_items(query)[:10]
    results = []
    for idx, (p, v) in enumerate(items):
        status = await fetch_version_status(p, v)
        results.append(
            InlineQueryResultArticle(
                id=str(idx),
                title=f"{p} {v or ''}".strip(),
                input_message_content=InputTextMessageContent(status),
                description=status.split('\n')[0][:60],
            )
        )
    await update.inline_query.answer(results, cache_time=300)

def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN не задан.")
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("check", check))
    app.add_handler(MessageHandler(filters.Document.FileExtension("txt"), check_file))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, check_message))
    app.add_handler(InlineQueryHandler(inline_query))

    app.run_polling()

if __name__ == "__main__":
    main()
