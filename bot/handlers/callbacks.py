"""Callback query handlers for inline keyboards."""
import logging
from telegram import Update
from telegram.ext import ContextTypes
from functools import wraps

from bot.services.monitoring_service import MonitoringService
from bot.services.version_service import VersionService
from bot.database.db import get_db

log = logging.getLogger(__name__)


def error_handler(func):
    """Decorator for error handling in handlers."""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        try:
            return await func(update, context, *args, **kwargs)
        except Exception as e:
            log.error(f"Error in {func.__name__}: {e}", exc_info=True)
            if update and update.callback_query:
                await update.callback_query.answer("Произошла ошибка", show_alert=True)
    return wrapper


@error_handler
async def callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle callback queries from inline keyboards."""
    query = update.callback_query
    if not query:
        return
    
    data = query.data
    user_id = update.effective_user.id
    
    # Get database session
    db_gen = get_db()
    db = next(db_gen)
    try:
        version_service = VersionService()
        monitoring_service = MonitoringService(db, version_service)
    
    if data.startswith("unsub_"):
        if data.startswith("unsub_id_"):
            # Unsubscribe by ID
            sub_id = int(data.split("_")[-1])
            success, message = await monitoring_service.unsubscribe(user_id, sub_id)
            await query.answer(message)
            if success:
                await query.edit_message_text("Подписка отменена.")
        else:
            # Unsubscribe by product/version
            parts = data.split("_")
            if len(parts) >= 3:
                slug = parts[1]
                ver = parts[2] if parts[2] != "all" else None
                # Find subscription
                subscriptions = await monitoring_service.get_user_subscriptions(user_id)
                for sub in subscriptions:
                    if sub.product_slug == slug and sub.version == ver:
                        success, message = await monitoring_service.unsubscribe(user_id, sub.id)
                        await query.answer(message)
                        if success:
                            await query.edit_message_text("Подписка отменена.")
                        return
                await query.answer("Подписка не найдена")
    else:
        await query.answer("Неизвестная команда")
    finally:
        db.close()

