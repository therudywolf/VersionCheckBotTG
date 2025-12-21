"""Main entry point for the Telegram bot."""
import asyncio
import logging
import signal
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
app = None  # Global app instance for shutdown
shutdown_event = None  # Will be created in the event loop


def setup_signal_handlers(loop):
    """Setup signal handlers for graceful shutdown."""
    def signal_handler(signum, frame):
        """Handle shutdown signals."""
        log.info(f"Received signal {signum}, initiating graceful shutdown...")
        if shutdown_event:
            loop.call_soon_threadsafe(shutdown_event.set)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)


async def post_init(app_instance):
    """Post-initialization callback for the application."""
    global scheduler, shutdown_event, version_service
    
    # Create shutdown event in the current event loop
    shutdown_event = asyncio.Event()
    
    # Setup signal handlers now that we have an event loop
    loop = asyncio.get_event_loop()
    setup_signal_handlers(loop)
    
    # Initialize cache directory and cleanup old files
    from pathlib import Path
    cache_dir = Path(settings.CACHE_DIR)
    cache_dir.mkdir(parents=True, exist_ok=True)
    log.info(f"Cache directory: {cache_dir.absolute()}")
    
    # Cleanup old cache files
    await version_service._cleanup_old_cache_files()
    
    # Start scheduler
    scheduler = Scheduler(app_instance.bot)
    await scheduler.start()
    
    log.info("Bot initialized and scheduler started")


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
    
    # Initialize default admin from config if exists
    if settings.ADMIN_IDS:
        from bot.database.db import get_db
        from bot.models.admin import Access, BotMode
        db_gen = get_db()
        db = next(db_gen)
        try:
            # Initialize bot mode if not exists
            bot_mode = db.query(BotMode).first()
            if not bot_mode:
                bot_mode = BotMode(mode="open")
                db.add(bot_mode)
                db.commit()
            
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
            log.error(f"Error initializing admins: {e}", exc_info=True)
            db.rollback()
        finally:
            db.close()
    
    global app
    app = (
        ApplicationBuilder()
        .token(settings.BOT_TOKEN)
        .concurrent_updates(True)
        .post_init(post_init)
        .post_shutdown(shutdown)
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
    
    # Run bot with graceful shutdown support
    # Signal handlers will be set up in post_init callback when event loop is available
    try:
        app.run_polling(
            close_loop=False,
            stop_signals=None  # We handle signals ourselves
        )
    except KeyboardInterrupt:
        log.info("Keyboard interrupt received")
    finally:
        if shutdown_event and not shutdown_event.is_set():
            shutdown_event.set()


async def shutdown():
    """Gracefully shutdown the bot."""
    log.info("Starting graceful shutdown...")
    
    # Stop accepting new updates
    global app
    if 'app' in globals() and app:
        try:
            await app.stop()
            await app.shutdown()
        except Exception as e:
            log.error(f"Error stopping app: {e}", exc_info=True)
    
    # Stop scheduler
    global scheduler
    if scheduler:
        try:
            await scheduler.stop()
        except Exception as e:
            log.error(f"Error stopping scheduler: {e}", exc_info=True)
    
    # Close version service
    global version_service
    if version_service:
        try:
            await version_service.close()
        except Exception as e:
            log.error(f"Error closing version service: {e}", exc_info=True)
    
    # Close database connections
    try:
        from bot.database.db import engine
        engine.dispose()
    except Exception as e:
        log.error(f"Error disposing database engine: {e}", exc_info=True)
    
    log.info("Shutdown complete")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log.info("Bot stopped by user")
    except Exception as e:
        log.error(f"Fatal error: {e}", exc_info=True)
    finally:
        # Ensure graceful shutdown
        try:
            asyncio.run(shutdown())
        except Exception as e:
            log.error(f"Error during shutdown: {e}", exc_info=True)
