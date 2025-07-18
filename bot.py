"""Telegram handlers — polished version."""
from __future__ import annotations

import asyncio
import logging

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InlineQueryResultArticle,
    InputTextMessageContent,
    Update,
)
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    InlineQueryHandler,
    MessageHandler,
    filters,
)

from config import settings
from services.eol import EolService
from utils.parser import parse
from utils.fuzzy import suggest

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger(__name__)

svc = EolService()


# --------------------------------------------------------------------- #
# helpers
async def _send_help(target, username: str) -> None:
    await target.reply_markdown(
        (
            "*Команды*\n"
            "/check `<список>` — проверить вручную\n"
            "Можно прислать .txt со списком.\n\n"
            "*Форматы*\n"
            "`python 3.13`, `python`\n"
            "`nodejs22`, `nodejs 22`\n\n"
            f"*Inline* — `@{username} nodejs`""
        ),
        disable_web_page_preview=True,
    )


# --------------------------------------------------------------------- #
# command handlers
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    kb = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("❓ Помощь", callback_data="help"),
                InlineKeyboardButton("🌐 endoflife.date", url="https://endoflife.date"),
            ]
        ]
    )
    await update.message.reply_markdown(
        "👋 *Привет!* Я показываю, поддерживается ли версия ПО.", reply_markup=kb
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _send_help(update.message, context.bot.username)


async def cmd_check(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _respond(update, " ".join(context.args))


# --------------------------------------------------------------------- #
# generic input handling
async def _respond(update: Update, text: str) -> None:
    items = parse(text)
    if not items:
        await update.message.reply_text("Не распознал продукты.")
        return

    # если все без версии — присылаем таблицы по отдельности
    if all(ver is None for _, ver in items):
        for slug, _ in items:
            data = await svc.releases(slug)
            if data:
                msg = svc.table(slug, data)
                await update.message.reply_markdown(msg, disable_web_page_preview=True)
            else:
                await update.message.reply_text(f"❌ {slug}: не найдено")
        return

    # иначе — сводка строкой
    sem = asyncio.Semaphore(settings.MAX_PARALLEL)

    async def job(slug: str, ver: str | None) -> str:
        async with sem:
            return await svc.status_line(slug, ver)

    lines = await asyncio.gather(*(job(s, v) for s, v in items))
    await update.message.reply_text("\n".join(lines))


# --------------------------------------------------------------------- #
# text / file
async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _respond(update, update.message.text or "")


async def on_file(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    doc = update.message.document
    if doc.mime_type != "text/plain":
        await update.message.reply_text("Только .txt файлы.")
        return
    content = await (await doc.get_file()).download_as_bytes()
    await _respond(update, content.decode("utf-8", "ignore"))


# --------------------------------------------------------------------- #
# inline
async def on_inline(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.inline_query.query.strip()
    if not query:
        return

    parsed = parse(query)
    slug, ver = parsed[0] if parsed else (query, None)

    choices = await svc.product_slugs()
    matches = suggest(slug, choices)

    results = []
    for idx, m in enumerate(matches):
        status = await svc.status_line(m, ver)
        results.append(
            InlineQueryResultArticle(
                id=str(idx),
                title=status.split("→")[0].strip("✅❌ "),
                description=status,
                input_message_content=InputTextMessageContent(status),
            )
        )
    await update.inline_query.answer(results, cache_time=120)


# --------------------------------------------------------------------- #
# button callbacks
async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.callback_query.data == "help":
        await _send_help(update.callback_query.message, context.bot.username)
        await update.callback_query.answer()


# --------------------------------------------------------------------- #
def main() -> None:
    if not settings.BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN не задан.")

    app = ApplicationBuilder().token(settings.BOT_TOKEN).concurrent_updates(True).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("check", cmd_check))

    app.add_handler(MessageHandler(filters.Document.FileExtension("txt"), on_file))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))

    app.add_handler(InlineQueryHandler(on_inline))
    app.add_handler(CallbackQueryHandler(on_callback))

    log.info("Bot is running…")
    app.run_polling(close_loop=False)


if __name__ == "__main__":
    try:
        main()
    finally:
        import asyncio

        asyncio.run(svc.close())
