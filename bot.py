import asyncio
import logging
from typing import List, Optional, Tuple

from telegram import InlineQueryResultArticle, InputTextMessageContent, Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    InlineQueryHandler,
    MessageHandler,
    filters,
)

from config import settings
from eol_service import EolService
from parser import parse_query
from fuzzy import find_best

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

eol_service: Optional[EolService] = None

async def on_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Я проверяю актуальность версий ПО (данные endoflife.date).\n"
        "Отправь мне, например:  `python 3.12, nodejs, nginx`\n"
        "Или используй inline: `@%s nodejs 20`" % context.bot.username,
        parse_mode='Markdown',
    )

async def on_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "/check <список> — проверить версии\n"
        "/reload — обновить кэш slugs\n"
        "Inline режим: @botname <slug> [версия]",
    )

async def on_check_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    qry = " ".join(context.args)
    await handle_text(update, context, qry)

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    if not text.strip():
        await update.message.reply_text("Нечего проверять 🧐")
        return
    items = parse_query(text)
    if not items:
        await update.message.reply_text("Не смог распознать продукты во входных данных.")
        return
    tasks = [eol_service.get_status(slug, ver) for slug, ver in items]
    statuses = await asyncio.gather(*tasks)
    await update.message.reply_text("\n".join(statuses))

async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await handle_text(update, context, update.message.text or "")

async def on_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    if doc.mime_type != "text/plain":
        await update.message.reply_text("Пока читаю только текстовые .txt файлы.")
        return
    file = await doc.get_file()
    content = await file.download_as_bytes()
    await handle_text(update, context, content.decode("utf-8", errors="ignore"))

async def inline_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.inline_query.query.strip()
    if not query:
        return
    items = parse_query(query)
    if not items:
        return
    slug, ver = items[0]
    # find best slugs suggestions
    slugs = await eol_service.list_products()
    matches = find_best(slug, slugs, limit=5)
    results = []
    idx = 0
    for match_slug, score in matches:
        status = await eol_service.get_status(match_slug, ver)
        results.append(
            InlineQueryResultArticle(
                id=f"{idx}",
                title=status.split("→")[0].strip("🔹 "),
                description=status,
                input_message_content=InputTextMessageContent(status),
            )
        )
        idx += 1
    await update.inline_query.answer(results, cache_time=300, is_personal=False)

async def reload_cache(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await eol_service._ensure_products()
    await update.message.reply_text("Кэш перечня продуктов обновлён.")

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    log.exception("Unhandled exception: %s", context.error)
    if isinstance(update, Update) and update.message:
        await update.message.reply_text("😔 Ошибка сервера. Попробуйте позже.")

async def main():
    global eol_service
    eol_service = await EolService().__aenter__()

    app = (
        ApplicationBuilder()
        .token(settings.BOT_TOKEN)
        .concurrent_updates(True)
        .build()
    )

    app.add_handler(CommandHandler("start", on_start))
    app.add_handler(CommandHandler("help", on_help))
    app.add_handler(CommandHandler("check", on_check_command))
    app.add_handler(CommandHandler("reload", reload_cache))
    app.add_handler(MessageHandler(filters.Document.FileExtension("txt"), on_file))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    app.add_handler(InlineQueryHandler(inline_query))
    app.add_error_handler(error_handler)

    log.info("Bot launched")
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    # run until Ctrl+C
    await app.updater.idle()
    await app.stop()
    await app.shutdown()
    await eol_service.__aexit__(None, None, None)

if __name__ == "__main__":
    asyncio.run(main())
