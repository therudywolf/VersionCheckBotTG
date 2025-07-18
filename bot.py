from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, CallbackQueryHandler

async def _send_help(target, username: str):
    help_text = (
        "*Команды*\n"
        "/check `<список>` — проверить вручную\n"
        "Можно прислать .txt со списком.\n\n"
        "*Форматы*\n"
        "`python 3.13`, `python`\n"
        "`nodejs22`, `nodejs 22`\n\n"
        f"*Inline* — `@{username} nodejs`"
    )
    await target.reply_markdown(help_text, disable_web_page_preview=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("❓ Помощь", callback_data="help")]])
    await update.message.reply_text("Hello", reply_markup=kb)

async def cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query.data == "help":
        await _send_help(update.callback_query.message, context.bot.username)
        await update.callback_query.answer()

def main():
    import os
    token = os.getenv("BOT_TOKEN")
    app = ApplicationBuilder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(cb))
    app.run_polling()

if __name__ == "__main__":
    main()
