import asyncio, logging
from telegram import InlineQueryResultArticle, InputTextMessageContent, Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, InlineQueryHandler, ContextTypes, filters
from config import settings
from eol_service import Eol
from parser import parse
from fuzzy import suggest

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)
eol = Eol()

async def start(update:Update, ctx:ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Я проверяю поддерживаемость версий ПО.\n"
        "Пример: nodejs 22, python\n"
        "Inline: @%s nginx" % ctx.bot.username
    )

async def check_cmd(update:Update, ctx:ContextTypes.DEFAULT_TYPE):
    text = " ".join(ctx.args)
    await respond(update, text)

async def respond(update:Update, text:str):
    items = parse(text)
    if not items:
        await update.message.reply_text("Не распознал продукты.")
        return
    res = await asyncio.gather(*(eol.status(s,v) for s,v in items))
    await update.message.reply_text("\n".join(res))

async def on_msg(update:Update, ctx:ContextTypes.DEFAULT_TYPE):
    await respond(update, update.message.text or "")

async def on_inline(update:Update, ctx:ContextTypes.DEFAULT_TYPE):
    q = update.inline_query.query.strip()
    if not q:
        return
    item = parse(q)[:1]
    if not item:
        return
    slug, ver = item[0]
    choices = await eol.list_products()
    options = suggest(slug, choices, 5)
    results = []
    for idx,(s,_) in enumerate(options):
        st = await eol.status(s, ver)
        results.append(
            InlineQueryResultArticle(
                id=str(idx),
                title=st.split("→")[0].strip("🔹 "),
                description=st,
                input_message_content=InputTextMessageContent(st),
            )
        )
    await update.inline_query.answer(results, cache_time=300)

async def reload_cmd(update:Update, ctx:ContextTypes.DEFAULT_TYPE):
    await eol.list_products()
    await update.message.reply_text("Список обновлён.")

async def err(update, ctx:ContextTypes.DEFAULT_TYPE):
    log.exception("Err: %s", ctx.error)
    if isinstance(update, Update) and update.message:
        await update.message.reply_text("Ошибка сервера.")

def main():
    if not settings.BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN env missing")
    app = ApplicationBuilder().token(settings.BOT_TOKEN).concurrent_updates(True).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("check", check_cmd))
    app.add_handler(CommandHandler("reload", reload_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_msg))
    app.add_handler(InlineQueryHandler(on_inline))
    app.add_error_handler(err)
    log.info("run")
    app.run_polling(close_loop=False)

if __name__=="__main__":
    try:
        main()
    finally:
        asyncio.run(eol.close())
