
    import asyncio
    import logging
    from typing import List

    from telegram import (
        InlineQueryResultArticle,
        InputTextMessageContent,
        Update,
    )
    from telegram.constants import ParseMode
    from telegram.ext import (
        ApplicationBuilder,
        CommandHandler,
        MessageHandler,
        InlineQueryHandler,
        ContextTypes,
        filters,
    )

    from config import settings
    from eol_py import Eol
    from parser import parse
    from fuzzy_py import sugg

    logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
    log = logging.getLogger(__name__)

    # Global service instance (reuse underlying aiohttp session)
    svc = Eol()


    # ---------------------------------------------------------------------------#
    # Helper utils
    # ---------------------------------------------------------------------------#
    BULLET_PREFIXES = ("-", "—", "•")

    def _split_bullets(text: str) -> List[str]:
        """Return list of lines if message looks like a bullet list."""
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        if len(lines) <= 1:
            return []
        if all(any(l.startswith(p) for p in BULLET_PREFIXES) for l in lines):
            # strip prefix
            return [l.lstrip(''.join(BULLET_PREFIXES)).strip() for l in lines]
        return []


    async def _respond_single(u: Update, query: str):
        """Handle a single product query and send a nicely formatted answer."""
        items = parse(query)
        if not items:
            await u.message.reply_text("⚠️ Не распознал ни одного продукта.")
            return

        if len(items) == 1:
            slug, ver = items[0]
            data = await svc.releases(slug)
            if data:
                table = svc.table(slug, data, highlight_version=ver)
                await u.message.reply_markdown(table, disable_web_page_preview=True)
                return

        # Multiple products – print a short status line each
        sem = asyncio.Semaphore(settings.MAX_PARALLEL)

        async def job(s, v):
            async with sem:
                return await svc.status_line(s, v)

        lines = await asyncio.gather(*(job(s, v) for s, v in items))
        await u.message.reply_text("\n".join(lines))


    # ---------------------------------------------------------------------------#
    # Command handlers
    # ---------------------------------------------------------------------------#
    async def cmd_start(u: Update, c: ContextTypes.DEFAULT_TYPE):
        text = (
            "*End‑of‑Life Bot 🇷🇺*
"
            "Я проверяю состояние поддержи версий ПО по данным [endoflife.date](https://endoflife.date/).

"
            "*Как пользоваться:*
"
            "• Отправьте сообщение вроде `nodejs 22, python` – получаете таблицу.
"
            "• Пришлите текстовый файл (.txt) с перечнем – проверю всё сразу.
"
            "• В инлайн‑режиме: `@{username} nodejs` – получите статус прямо в другом чате.

"
            "Доступные команды:
"
            "  /start – краткая справка
"
            "  /help  – полная помощь"
        ).format(username=c.bot.username)
        await u.message.reply_markdown(text, disable_web_page_preview=True)


    async def cmd_help(u: Update, c: ContextTypes.DEFAULT_TYPE):
        text = (
            "*Подробная справка*

"
            "Бот обращается к публичному API https://endoflife.date, чтобы показать сроки "
            "поддержки (EOL) разных продуктов.

"
            "📋 *Форматы ввода*
"
            "• `nodejs 20` – продукт + версия
"
            "• `python` – только продукт (покажу состояние последней стабильной версии)
"
            "• `- docker\n- kubernetes\n- postgres` – маркированный список; вы получите "
            "отдельное сообщение для каждого пункта.

"
            "📎 Можно прислать *.txt* файл с перечнем продуктов.

"
            "🔎 *Инлайн‑режим*
"
            "В любом чате наберите `@{username} <продукт>` – появятся подсказки.

"
            "Исходники: https://github.com/therudywolf/versionbot"
        ).format(username=c.bot.username)
        await u.message.reply_markdown(text, disable_web_page_preview=True)


    # ---------------------------------------------------------------------------#
    # Message handlers
    # ---------------------------------------------------------------------------#
    async def on_text(u: Update, c: ContextTypes.DEFAULT_TYPE):
        txt = u.message.text or ""
        bullets = _split_bullets(txt)
        if bullets:
            # Process each bullet separately – nice when list is long
            for item in bullets:
                await _respond_single(u, item)
            return
        await _respond_single(u, txt)


    async def on_file(u: Update, c: ContextTypes.DEFAULT_TYPE):
        doc = u.message.document
        if doc.mime_type != "text/plain":
            await u.message.reply_text("📄 Принимаются только .txt файлы.")
            return
        content = await (await doc.get_file()).download_as_bytes()
        await _respond_single(u, content.decode("utf-8", "ignore"))


    # ---------------------------------------------------------------------------#
    # Inline‑mode
    # ---------------------------------------------------------------------------#
    async def on_inline(u: Update, c: ContextTypes.DEFAULT_TYPE):
        q = u.inline_query.query.strip()
        if not q:
            return

        # Try to parse “product version”; fallback to assuming entire query is product
        parsed = parse(q)
        slug, ver = parsed[0] if parsed else (q, None)

        # Autocomplete top 5 closest matches
        products = await svc.products()
        best = sugg(slug, products, n=5)

        results = []
        for idx, s in enumerate(best):
            status = await svc.status_line(s, ver)
            results.append(
                InlineQueryResultArticle(
                    id=str(idx),
                    title=status.split("→")[0].strip("✅❌ "),
                    description=status,
                    input_message_content=InputTextMessageContent(
                        status, parse_mode=ParseMode.MARKDOWN
                    ),
                )
            )
        await u.inline_query.answer(results, cache_time=60)


    # ---------------------------------------------------------------------------#
    # Bootstrap
    # ---------------------------------------------------------------------------#
    def main():
        if not settings.BOT_TOKEN:
            raise RuntimeError("BOT_TOKEN не установлен")

        app = (
            ApplicationBuilder()
            .token(settings.BOT_TOKEN)
            .concurrent_updates(True)
            .build()
        )

        # Register handlers
        app.add_handler(CommandHandler("start", cmd_start))
        app.add_handler(CommandHandler("help", cmd_help))
        app.add_handler(MessageHandler(filters.Document.FileExtension("txt"), on_file))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
        app.add_handler(InlineQueryHandler(on_inline))

        log.info("🤖 Bot is running...")
        app.run_polling(close_loop=False)


    if __name__ == "__main__":
        try:
            main()
        finally:
            # Close underlying HTTP session gracefully
            asyncio.run(svc.close())
