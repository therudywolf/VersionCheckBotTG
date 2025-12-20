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
    # Validate configuration
    from config import validate_config
    try:
        validate_config()
        log.info("Configuration validated successfully")
    except Exception as e:
        log.error(f"Configuration validation failed: {e}")
        raise
    
    if not settings.BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN не установлен")
    
    # Initialize database
    log.info("Initializing database...")
    init_db()
    
    # Initialize cache directory and cleanup old files
    from pathlib import Path
    from bot.services.version_service import VersionService
    cache_dir = Path(settings.CACHE_DIR)
    cache_dir.mkdir(parents=True, exist_ok=True)
    log.info(f"Cache directory: {cache_dir.absolute()}")
    
    # Cleanup old cache files
    version_service = VersionService()
    asyncio.run(version_service._cleanup_old_cache_files())
    
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
    
    global app
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
    app.add_handler(CommandHandler("health", commands.health_command))
    app.add_handler(CommandHandler("stats", commands.stats_command))
    app.add_handler(CommandHandler("admin", commands.admin_command))
    app.add_handler(MessageHandler(filters.Document.FileExtension("txt"), messages.file_message))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, messages.text_message))
    app.add_handler(InlineQueryHandler(inline.inline_query))
    app.add_handler(CallbackQueryHandler(callbacks.callback_query))
    
    log.info("Bot starting...")
    
    # Setup signal handlers for graceful shutdown
    def signal_handler(signum, frame):
        """Handle shutdown signals."""
        log.info(f"Received signal {signum}, initiating graceful shutdown...")
        shutdown_event.set()
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Start scheduler
    global scheduler
    scheduler = Scheduler(app.bot)
    asyncio.create_task(scheduler.start())
    
    # Run bot with graceful shutdown support
    try:
        app.run_polling(close_loop=False, stop_signals=None)  # We handle signals ourselves
    except KeyboardInterrupt:
        log.info("Keyboard interrupt received")
    finally:
        shutdown_event.set()


async def shutdown():
    """Gracefully shutdown the bot."""
    log.info("Starting graceful shutdown...")
    
    # Stop accepting new updates
    if app:
        await app.stop()
        await app.shutdown()
    
    # Stop scheduler
    global scheduler
    if scheduler:
        await scheduler.stop()
    
    # Close version service
    global version_service
    if version_service:
        await version_service.close()
    
    # Close database connections
    from bot.database.db import engine
    engine.dispose()
    
    log.info("Shutdown complete")


if __name__ == "__main__":
    try:
        main()
        
        # Wait for shutdown signal
        try:
            asyncio.run(shutdown_event.wait())
        except KeyboardInterrupt:
            pass
        
    except KeyboardInterrupt:
        log.info("Bot stopped by user")
    except Exception as e:
        log.error(f"Fatal error: {e}", exc_info=True)
    finally:
        asyncio.run(shutdown())
