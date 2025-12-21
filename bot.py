"""Main entry point for the Telegram bot."""
import asyncio
import logging
import signal
import json
from pathlib import Path
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

# Debug logging setup
DEBUG_LOG_PATH = Path(".cursor/debug.log")
def debug_log(location, message, data=None, hypothesis_id=None):
    """Write debug log entry."""
    try:
        import time
        import os
        # Use absolute path to ensure it works from any directory
        abs_path = Path(__file__).parent / DEBUG_LOG_PATH
        abs_path.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "timestamp": int(time.time() * 1000),
            "location": location,
            "message": message,
            "data": data or {},
            "sessionId": "debug-session",
            "runId": "run1",
            "hypothesisId": hypothesis_id
        }
        with open(abs_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception as e:
        # Log to stderr so we can see if debug logging fails
        import sys
        print(f"DEBUG LOG ERROR: {e}", file=sys.stderr)

# Global service instance
version_service = VersionService()
scheduler = None
app = None  # Global app instance for shutdown
shutdown_event = None  # Will be created in the event loop


def setup_signal_handlers(loop):
    """Setup signal handlers for graceful shutdown."""
    # #region agent log
    debug_log("bot.py:32", "setup_signal_handlers called", {"loop_exists": loop is not None, "shutdown_event_exists": shutdown_event is not None}, "A")
    # #endregion
    
    def signal_handler(signum, frame):
        """Handle shutdown signals."""
        # #region agent log
        debug_log("bot.py:36", "signal_handler called", {"signum": signum, "shutdown_event_is_none": shutdown_event is None}, "A")
        # #endregion
        log.info(f"Received signal {signum}, initiating graceful shutdown...")
        if shutdown_event:
            # #region agent log
            debug_log("bot.py:40", "Setting shutdown_event", {}, "D")
            # #endregion
            loop.call_soon_threadsafe(shutdown_event.set)
        else:
            # #region agent log
            debug_log("bot.py:43", "shutdown_event is None, cannot set", {}, "A")
            # #endregion
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    # #region agent log
    debug_log("bot.py:47", "Signal handlers registered", {"SIGINT": True, "SIGTERM": True}, "A")
    # #endregion


async def post_init(app_instance):
    """Post-initialization callback for the application."""
    # #region agent log
    debug_log("bot.py:44", "post_init entry", {"app_instance_exists": app_instance is not None}, "B")
    # #endregion
    global scheduler, shutdown_event, version_service
    
    # Create shutdown event in the current event loop
    shutdown_event = asyncio.Event()
    # #region agent log
    debug_log("bot.py:50", "shutdown_event created", {"shutdown_event_is_none": shutdown_event is None}, "A")
    # #endregion
    
    # Setup signal handlers now that we have an event loop
    loop = asyncio.get_event_loop()
    # #region agent log
    debug_log("bot.py:54", "Got event loop", {"loop_exists": loop is not None}, "B")
    # #endregion
    setup_signal_handlers(loop)
    
    # Initialize cache directory and cleanup old files
    from pathlib import Path
    cache_dir = Path(settings.CACHE_DIR)
    cache_dir.mkdir(parents=True, exist_ok=True)
    log.info(f"Cache directory: {cache_dir.absolute()}")
    # #region agent log
    debug_log("bot.py:62", "Cache directory initialized", {"cache_dir": str(cache_dir.absolute()), "exists": cache_dir.exists()}, "C")
    # #endregion
    
    # Cleanup old cache files
    # #region agent log
    debug_log("bot.py:65", "Starting cache cleanup", {}, "B")
    # #endregion
    await version_service._cleanup_old_cache_files()
    # #region agent log
    debug_log("bot.py:67", "Cache cleanup completed", {}, "B")
    # #endregion
    
    # Start scheduler
    # #region agent log
    debug_log("bot.py:70", "Creating scheduler", {"bot_exists": app_instance.bot is not None}, "B")
    # #endregion
    scheduler = Scheduler(app_instance.bot)
    # #region agent log
    debug_log("bot.py:72", "Scheduler created, starting", {"scheduler_exists": scheduler is not None}, "B")
    # #endregion
    await scheduler.start()
    # #region agent log
    debug_log("bot.py:74", "Scheduler started", {"scheduler_running": getattr(scheduler, 'running', False)}, "B")
    # #endregion
    
    log.info("Bot initialized and scheduler started")


def main():
    """Initialize and run the bot."""
    # #region agent log
    debug_log("bot.py:71", "main() entry", {}, "E")
    # #endregion
    # Validate configuration
    from config import validate_config
    try:
        # #region agent log
        debug_log("bot.py:76", "Validating config", {}, "E")
        # #endregion
        validate_config()
        log.info("Configuration validated successfully")
        # #region agent log
        debug_log("bot.py:79", "Config validation success", {}, "E")
        # #endregion
    except Exception as e:
        log.error(f"Configuration validation failed: {e}")
        # #region agent log
        debug_log("bot.py:82", "Config validation failed", {"error": str(e)}, "E")
        # #endregion
        raise
    
    if not settings.BOT_TOKEN:
        # #region agent log
        debug_log("bot.py:87", "BOT_TOKEN missing", {}, "E")
        # #endregion
        raise RuntimeError("BOT_TOKEN не установлен")
    
    # Initialize database
    log.info("Initializing database...")
    # #region agent log
    debug_log("bot.py:92", "Initializing database", {"database_url": settings.DATABASE_URL}, "C")
    # #endregion
    init_db()
    # #region agent log
    debug_log("bot.py:94", "Database initialized", {}, "C")
    # #endregion
    
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
    # #region agent log
    debug_log("bot.py:125", "Creating Application", {"has_token": bool(settings.BOT_TOKEN)}, "E")
    # #endregion
    app = (
        ApplicationBuilder()
        .token(settings.BOT_TOKEN)
        .concurrent_updates(True)
        .post_init(post_init)
        .post_shutdown(shutdown)
        .build()
    )
    # #region agent log
    debug_log("bot.py:133", "Application created", {"app_exists": app is not None}, "E")
    # #endregion
    
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
    # favorites_command, alerts_command, history_command - handlers not implemented yet
    # app.add_handler(CommandHandler("favorites", commands.favorites_command))
    # app.add_handler(CommandHandler("alerts", commands.alerts_command))
    # app.add_handler(CommandHandler("history", commands.history_command))
    app.add_handler(CommandHandler("health", commands.health_command))
    app.add_handler(CommandHandler("stats", commands.stats_command))
    app.add_handler(CommandHandler("admin", commands.admin_command))
    app.add_handler(MessageHandler(filters.Document.FileExtension("txt"), messages.file_message))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, messages.text_message))
    app.add_handler(InlineQueryHandler(inline.inline_query))
    app.add_handler(CallbackQueryHandler(callbacks.callback_query))
    
    log.info("Bot starting...")
    # #region agent log
    debug_log("bot.py:157", "Starting run_polling", {}, "B")
    # #endregion
    
    # Run bot with graceful shutdown support
    # Signal handlers will be set up in post_init callback when event loop is available
    try:
        app.run_polling(
            close_loop=False,
            stop_signals=None  # We handle signals ourselves
        )
    except KeyboardInterrupt:
        log.info("Keyboard interrupt received")
        # #region agent log
        debug_log("bot.py:167", "KeyboardInterrupt caught", {}, "D")
        # #endregion
    finally:
        # #region agent log
        debug_log("bot.py:170", "main() finally block", {"shutdown_event_exists": shutdown_event is not None, "shutdown_event_is_set": shutdown_event.is_set() if shutdown_event else None}, "D")
        # #endregion
        if shutdown_event and not shutdown_event.is_set():
            shutdown_event.set()
            # #region agent log
            debug_log("bot.py:173", "Set shutdown_event in finally", {}, "D")
            # #endregion


async def shutdown():
    """Gracefully shutdown the bot."""
    # #region agent log
    debug_log("bot.py:168", "shutdown() entry", {}, "D")
    # #endregion
    log.info("Starting graceful shutdown...")
    
    # Stop accepting new updates
    global app
    try:
        app_ref = globals().get('app')
    except:
        app_ref = None
    if app_ref:
        try:
            # #region agent log
            debug_log("bot.py:294", "Stopping app", {}, "D")
            # #endregion
            # Check if app is running before trying to stop it
            if hasattr(app_ref, '_running') and app_ref._running:
                await app_ref.stop()
            await app_ref.shutdown()
            # #region agent log
            debug_log("bot.py:300", "App stopped", {}, "D")
            # #endregion
        except RuntimeError as e:
            # App is not running - this is OK during error shutdown
            if "not running" not in str(e).lower():
                log.error(f"Error stopping app: {e}", exc_info=True)
                # #region agent log
                debug_log("bot.py:305", "Error stopping app", {"error": str(e)}, "D")
                # #endregion
        except Exception as e:
            log.error(f"Error stopping app: {e}", exc_info=True)
            # #region agent log
            debug_log("bot.py:310", "Error stopping app", {"error": str(e)}, "D")
            # #endregion
    
    # Stop scheduler
    global scheduler
    if scheduler:
        try:
            # #region agent log
            debug_log("bot.py:188", "Stopping scheduler", {}, "D")
            # #endregion
            await scheduler.stop()
            # #region agent log
            debug_log("bot.py:190", "Scheduler stopped", {}, "D")
            # #endregion
        except Exception as e:
            log.error(f"Error stopping scheduler: {e}", exc_info=True)
            # #region agent log
            debug_log("bot.py:193", "Error stopping scheduler", {"error": str(e)}, "D")
            # #endregion
    
    # Close version service
    global version_service
    if version_service:
        try:
            # #region agent log
            debug_log("bot.py:199", "Closing version service", {}, "D")
            # #endregion
            await version_service.close()
            # #region agent log
            debug_log("bot.py:201", "Version service closed", {}, "D")
            # #endregion
        except Exception as e:
            log.error(f"Error closing version service: {e}", exc_info=True)
            # #region agent log
            debug_log("bot.py:204", "Error closing version service", {"error": str(e)}, "D")
            # #endregion
    
    # Close database connections
    try:
        # #region agent log
        debug_log("bot.py:210", "Disposing database engine", {}, "D")
        # #endregion
        from bot.database.db import engine
        engine.dispose()
        # #region agent log
        debug_log("bot.py:213", "Database engine disposed", {}, "D")
        # #endregion
    except Exception as e:
        log.error(f"Error disposing database engine: {e}", exc_info=True)
        # #region agent log
        debug_log("bot.py:216", "Error disposing database", {"error": str(e)}, "D")
        # #endregion
    
    log.info("Shutdown complete")
    # #region agent log
    debug_log("bot.py:220", "shutdown() complete", {}, "D")
    # #endregion


if __name__ == "__main__":
    # #region agent log
    debug_log("bot.py:207", "__main__ entry", {}, "E")
    # #endregion
    try:
        main()
        # #region agent log
        debug_log("bot.py:210", "main() completed", {}, "E")
        # #endregion
    except KeyboardInterrupt:
        log.info("Bot stopped by user")
        # #region agent log
        debug_log("bot.py:213", "KeyboardInterrupt in __main__", {}, "D")
        # #endregion
    except Exception as e:
        log.error(f"Fatal error: {e}", exc_info=True)
        # #region agent log
        debug_log("bot.py:216", "Fatal error in __main__", {"error": str(e)}, "E")
        # #endregion
    finally:
        # Ensure graceful shutdown
        # #region agent log
        debug_log("bot.py:220", "__main__ finally block", {}, "D")
        # #endregion
        try:
            asyncio.run(shutdown())
            # #region agent log
            debug_log("bot.py:223", "shutdown() completed in finally", {}, "D")
            # #endregion
        except Exception as e:
            log.error(f"Error during shutdown: {e}", exc_info=True)
            # #region agent log
            debug_log("bot.py:226", "Error in shutdown()", {"error": str(e)}, "D")
            # #endregion
