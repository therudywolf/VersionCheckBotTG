import asyncio, logging
from telegram import InlineQueryResultArticle, InputTextMessageContent, Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, InlineQueryHandler, ContextTypes, filters
from config import settings
from eol_py import Eol
from parser import parse
from fuzzy_py import sugg

logging.basicConfig(level=logging.INFO)
log=logging.getLogger(__name__)
svc=Eol()

async def start(u:Update,c:ContextTypes.DEFAULT_TYPE):
    await u.message.reply_markdown(
        "Проверяю поддерживаемость версий ПО по endoflife.date.\n"
        "*Пример:* `nodejs 22, python`\n"
        "*Inline:*  `@%s nodejs`" % c.bot.username)

async def respond(u:Update, txt:str):
    items=parse(txt)
    if not items:
        await u.message.reply_text("Не распознал продукты.")
        return
    if len(items)==1:
        slug,ver=items[0]
        data=await svc.releases(slug)
        if data:
            table=svc.table(slug,data,highlight_version=ver)
            await u.message.reply_markdown(table)
            return
    sem=asyncio.Semaphore(settings.MAX_PARALLEL)
    async def job(s,v):
        async with sem:
            return await svc.status_line(s,v)
    lines=await asyncio.gather(*(job(s,v) for s,v in items))
    await u.message.reply_text("\n".join(lines))

async def check_cmd(u:Update,c:ContextTypes.DEFAULT_TYPE):
    await respond(u," ".join(c.args))

async def text_msg(u:Update,c:ContextTypes.DEFAULT_TYPE):
    await respond(u,u.message.text or "")

async def file_msg(u:Update,c:ContextTypes.DEFAULT_TYPE):
    doc=u.message.document
    if doc.mime_type!="text/plain":
        await u.message.reply_text("Нужен .txt файл.")
        return
    content=await (await doc.get_file()).download_as_bytes()
    await respond(u,content.decode('utf-8','ignore'))

async def inline_q(u:Update,c:ContextTypes.DEFAULT_TYPE):
    q=u.inline_query.query.strip()
    if not q: return
    slug,ver=parse(q)[:1][0] if parse(q) else (q,None)
    choices=await svc.products()
    best=sugg(slug,choices)
    results=[]
    for idx,s in enumerate(best):
        status=await svc.status_line(s,ver)
        results.append(
            InlineQueryResultArticle(
                id=str(idx),
                title=status.split('→')[0].strip('✅❌ '),
                description=status,
                input_message_content=InputTextMessageContent(status)))
    await u.inline_query.answer(results, cache_time=120)

def main():
    if not settings.BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN не установлен")
    app=ApplicationBuilder().token(settings.BOT_TOKEN).concurrent_updates(True).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("check", check_cmd))
    app.add_handler(MessageHandler(filters.Document.FileExtension("txt"), file_msg))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_msg))
    app.add_handler(InlineQueryHandler(inline_q))
    log.info("Run bot")
    app.run_polling(close_loop=False)

if __name__=="__main__":
    try:
        main()
    finally:
        asyncio.run(svc.close())
