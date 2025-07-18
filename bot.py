import asyncio, logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, InlineQueryResultArticle, InputTextMessageContent, Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, InlineQueryHandler, ContextTypes, filters
from config import settings
from eol_service import Eol
from parser import parse
from fuzzy_py import suggest

logging.basicConfig(level=logging.INFO)
log=logging.getLogger(__name__)
svc=Eol()

HELP_TEXT = (
    "*Команды*\n"
    "/check `<список>` — проверить вручную\n"
    "Можно прислать .txt файл со списком.\n\n"
    "*Форматы ввода*\n"
    "• `python 3.13`, `python`\n"
    "• `nodejs22`, `nodejs 22`\n"
    "• Разделители: запятые, пробелы, перевод строки\n\n"
    "*Inline* — в любом чате напишите `@%s nodejs`."
)

async def cmd_start(u:Update,c:ContextTypes.DEFAULT_TYPE):
    kb=InlineKeyboardMarkup(
        [[InlineKeyboardButton("❓ Помощь", callback_data="help"),
          InlineKeyboardButton("🌐 Сайт endoflife.date", url="https://endoflife.date")]]
    )
    await u.message.reply_markdown(
        "👋 *Привет!* Я показываю, поддерживается ли версия ПО.",
        reply_markup=kb
    )

async def help_msg(chat, username):
    await chat.reply_markdown(HELP_TEXT % username, disable_web_page_preview=True)

async def on_callback(u:Update,c:ContextTypes.DEFAULT_TYPE):
    if u.callback_query.data=="help":
        await help_msg(u.callback_query.message, c.bot.username)
        await u.callback_query.answer()

async def cmd_help(u:Update,c:ContextTypes.DEFAULT_TYPE):
    await help_msg(u.message, c.bot.username)

async def reply_for(u:Update, text:str):
    items=parse(text)
    if not items:
        await u.message.reply_text("Не распознал продукты.")
        return
    if all(v is None for _,v in items):
        # tables per slug
        for slug,_ in items:
            data=await svc.releases(slug)
            if data:
                tbl=svc.fancy_table(slug,data)
                await u.message.reply_markdown(tbl, disable_web_page_preview=True)
            else:
                await u.message.reply_text(f"❌ {slug}: не найдено")
        return
    # mixed or versions present: joint summary
    sem=asyncio.Semaphore(settings.MAX_PARALLEL)
    async def job(s,v):
        async with sem: return await svc.status_line(s,v)
    lines=await asyncio.gather(*(job(s,v) for s,v in items))
    await u.message.reply_text("\n".join(lines))

async def cmd_check(u:Update,c:ContextTypes.DEFAULT_TYPE):
    await reply_for(u," ".join(c.args))

async def on_text(u:Update,c:ContextTypes.DEFAULT_TYPE):
    await reply_for(u,u.message.text or "")

async def on_file(u:Update,c:ContextTypes.DEFAULT_TYPE):
    doc=u.message.document
    if doc.mime_type!="text/plain":
        await u.message.reply_text("Только .txt файлы.")
        return
    data=await (await doc.get_file()).download_as_bytes()
    await reply_for(u,data.decode('utf-8','ignore'))

async def on_inline(u:Update,c:ContextTypes.DEFAULT_TYPE):
    q=u.inline_query.query.strip()
    if not q: return
    slug,ver=parse(q)[:1][0] if parse(q) else (q,None)
    choices=await svc.products()
    opts=suggest(slug, choices)
    results=[]
    for idx,s in enumerate(opts):
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
        raise RuntimeError("BOT_TOKEN не задан.")
    app=ApplicationBuilder().token(settings.BOT_TOKEN).concurrent_updates(True).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("check", cmd_check))
    app.add_handler(MessageHandler(filters.Document.FileExtension("txt"), on_file))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    app.add_handler(InlineQueryHandler(on_inline))
    app.add_handler(filters.CallbackQueryHandler(on_callback))
    log.info("Bot running")
    app.run_polling(close_loop=False)

if __name__=="__main__":
    import asyncio
    try:
        main()
    finally:
        asyncio.run(svc.close())
