"""Main entry point for the Telegram bot."""
import asyncio
import logging
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    InlineQueryHandler,
    CallbackQueryHandler,
    filters,
)

from config import settings
from bot.handlers import commands, messages, inline, callbacks
from bot.services.version_service import VersionService
from bot.utils.logging_config import setup_logging
from bot.database.db import init_db
from bot.scheduler.tasks import Scheduler

# Setup logging
setup_logging()
log = logging.getLogger(__name__)

# Global service instance
version_service = VersionService()
scheduler = None


def main():
    """Initialize and run the bot."""
    if not settings.BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN не установлен")
    
    # Initialize database
    log.info("Initializing database...")
    init_db()
    
    # Initialize default admin from config if exists
    if settings.ADMIN_IDS:
        from bot.database.db import get_db
        from bot.models.admin import Access, BotMode
        db = next(get_db())
        try:
            # Initialize bot mode if not exists
            bot_mode = db.query(BotMode).first()
            if not bot_mode:
                bot_mode = BotMode(mode="open")
                db.add(bot_mode)
            
            for admin_id in settings.ADMIN_IDS:
                existing = db.query(Access).filter(Access.user_id == admin_id).first()
                if not existing:
                    admin = Access(
                        user_id=admin_id,
                        has_access=True,
                        is_admin=True,
                        notes="Initial admin from config"
                    )
                    db.add(admin)
                    log.info(f"Created initial admin: {admin_id}")
            db.commit()
        except Exception as e:
            log.error(f"Error initializing admins: {e}")
            db.rollback()
        finally:
            db.close()
    
    app = (
        ApplicationBuilder()
        .token(settings.BOT_TOKEN)
        .concurrent_updates(True)
        .build()
    )
    
    # Register handlers
    app.add_handler(CommandHandler("start", commands.start_command))
    app.add_handler(CommandHandler("help", commands.help_command))
    app.add_handler(CommandHandler("check", commands.check_command))
    app.add_handler(CommandHandler("subscribe", commands.subscribe_command))
    app.add_handler(CommandHandler("subscriptions", commands.subscriptions_command))
    app.add_handler(CommandHandler("export", commands.export_command))
    app.add_handler(CommandHandler("import", commands.import_command))
    app.add_handler(CommandHandler("compare", commands.compare_command))
    app.add_handler(CommandHandler("cve", commands.cve_command))
    app.add_handler(CommandHandler("favorites", commands.favorites_command))
    app.add_handler(CommandHandler("alerts", commands.alerts_command))
    app.add_handler(CommandHandler("history", commands.history_command))
    app.add_handler(CommandHandler("stats", commands.stats_command))
    app.add_handler(CommandHandler("admin", commands.admin_command))
    app.add_handler(MessageHandler(filters.Document.FileExtension("txt"), messages.file_message))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, messages.text_message))
    app.add_handler(InlineQueryHandler(inline.inline_query))
    app.add_handler(CallbackQueryHandler(callbacks.callback_query))
    
    log.info("Bot starting...")
    
    # Start scheduler
    global scheduler
    scheduler = Scheduler(app.bot)
    asyncio.create_task(scheduler.start())
    
    app.run_polling(close_loop=False)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log.info("Bot stopped by user")
    finally:
        if scheduler:
            asyncio.run(scheduler.stop())
        asyncio.run(version_service.close())
