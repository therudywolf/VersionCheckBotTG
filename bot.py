import asyncio, logging, math
from telegram import InlineQueryResultArticle, InputTextMessageContent, Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, InlineQueryHandler, filters
from config import settings
from eol_service import EolService
from parser import parse
from fuzzy import suggest

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)
svc = EolService()

async def start(u:Update,c:ContextTypes.DEFAULT_TYPE):
    await u.message.reply_markdown(
        "Я проверяю поддерживаемость версий ПО.\n"
        "*Примеры:*  `nodejs 22, python`\n"
        "*Inline:*   `@%s nodejs`" % c.bot.username)

async def reply_status(u:Update, text:str):
    items = parse(text)
    if not items:
        await u.message.reply_text("Не распознал продукты.")
        return
    if len(items)==1 and items[0][1] is None:
        # show table view
        slug,_ = items[0]
        data = await svc.release_data(slug)
        if data is None:
            await u.message.reply_text(f"❌ {slug}: не найдено")
            return
        table = svc.make_table(slug, data)
        await u.message.reply_markdown(table, disable_web_page_preview=True)
        return
    sem = asyncio.Semaphore(settings.MAX_PARALLEL)
    async def task(slug,ver):
        async with sem:
            return await svc.status_line(slug,ver)
    lines = await asyncio.gather(*(task(s,v) for s,v in items))
    await u.message.reply_text("\n".join(lines))

async def cmd_check(u:Update,c:ContextTypes.DEFAULT_TYPE):
    await reply_status(u," ".join(c.args))

async def on_text(u:Update,c:ContextTypes.DEFAULT_TYPE):
    await reply_status(u,u.message.text or "")

async def on_file(u:Update,c:ContextTypes.DEFAULT_TYPE):
    doc=u.message.document
    if doc.mime_type!="text/plain":
        await u.message.reply_text("Принимаю только .txt")
        return
    file=await doc.get_file()
    data=await file.download_as_bytes()
    await reply_status(u,data.decode('utf-8','ignore'))

async def on_inline(u:Update,c:ContextTypes.DEFAULT_TYPE):
    q=u.inline_query.query.strip()
    if not q: return
    slug,ver=parse(q)[:1][0] if parse(q) else (q,None)
    choices=await svc.products()
    for s,_ in suggest(slug,choices,n=5): break
    matches = [m for m,_ in suggest(slug, choices, n=5)]
    results=[]
    for idx,m in enumerate(matches):
        status=await svc.status_line(m,ver)
        results.append(
            InlineQueryResultArticle(
                id=str(idx),
                title=status.split('→')[0].strip('✅❌ ').strip(),
                description=status,
                input_message_content=InputTextMessageContent(status)))
    await u.inline_query.answer(results, cache_time=120)

async def error(update, context):
    log.error("Exception: %s", context.error)

def main():
    if not settings.BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN missing")
    app=ApplicationBuilder().token(settings.BOT_TOKEN).concurrent_updates(True).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("check", cmd_check))
    app.add_handler(MessageHandler(filters.Document.FileExtension("txt"), on_file))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    app.add_handler(InlineQueryHandler(on_inline))
    app.add_error_handler(error)
    log.info("Running bot")
    app.run_polling(close_loop=False)

if __name__=="__main__":
    try:
        main()
    finally:
        asyncio.run(svc.close())
