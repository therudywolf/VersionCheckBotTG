"""Callback query handlers for inline keyboards."""
import logging
from typing import Any
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
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args: Any, **kwargs: Any) -> Any:
        try:
            return await func(update, context, *args, **kwargs)
        except Exception as e:
            log.error(f"Error in {func.__name__}: {e}", exc_info=True)
            if update and update.callback_query:
                await update.callback_query.answer("Произошла ошибка", show_alert=True)
    return wrapper


@error_handler
async def callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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
    elif data.startswith("sub_"):
        # Subscribe from inline query
        parts = data.split("_")
        if len(parts) >= 3:
            slug = parts[1]
            ver = parts[2] if parts[2] != "all" else None
            success, message = await monitoring_service.subscribe(user_id, slug, ver)
            await query.answer(message)
            if success:
                await query.edit_message_text(f"✅ Подписка на {slug}" + (f" {ver}" if ver else "") + " создана")
    elif data.startswith("detail_"):
        # Show details
        parts = data.split("_")
        if len(parts) >= 3:
            slug = parts[1]
            ver = parts[2] if parts[2] != "all" else None
            from bot.services.version_service import VersionService
            version_service = VersionService()
            data_releases = await version_service.releases(slug)
            if data_releases:
                table = version_service.table(slug, data_releases, highlight_version=ver)
                await query.answer()
                await query.edit_message_text(table, parse_mode="Markdown")
            else:
                await query.answer("Данные не найдены")
    elif data.startswith("subs_page_"):
        # Pagination for subscriptions
        page = int(data.split("_")[-1])
        from bot.handlers.commands import subscriptions_command
        context.args = [str(page)]
        await subscriptions_command(update, context)
    elif data.startswith("cve_page_"):
        # Pagination for CVE
        parts = data.split("_")
        if len(parts) >= 4:
            page = int(parts[-1])
            slug = parts[2]
            ver = parts[3] if parts[3] != "all" else None
            from bot.handlers.commands import cve_command
            context.args = [slug]
            if ver:
                context.args.append(ver)
            context.args.append(str(page))
            await cve_command(update, context)
    elif data.startswith("fav_remove_"):
        # Remove favorite
        fav_id = int(data.split("_")[-1])
        from bot.models import Favorite
        favorite = db.query(Favorite).filter(
            Favorite.id == fav_id,
            Favorite.user_id == user_id
        ).first()
        
        if favorite:
            db.delete(favorite)
            db.commit()
            await query.answer("Удалено из избранного")
            await query.edit_message_text("✅ Удалено из избранного.")
        else:
            await query.answer("Не найдено")
    elif data.startswith("check_"):
        # Quick check from favorites
        parts = data.split("_")
        if len(parts) >= 3:
            slug = parts[1]
            ver = parts[2] if parts[2] != "all" else None
            from bot.services.version_service import VersionService
            version_service = VersionService()
            data_releases = await version_service.releases(slug)
            if data_releases:
                table = version_service.table(slug, data_releases, highlight_version=ver)
                await query.answer()
                await query.edit_message_text(table, parse_mode="Markdown")
            else:
                await query.answer("Данные не найдены")
    elif data.startswith("alert_toggle_"):
        # Toggle alert settings
        setting = data.split("_")[-1]
        from bot.models import UserSettings
        
        settings = db.query(UserSettings).filter(UserSettings.user_id == user_id).first()
        if not settings:
            settings = UserSettings(user_id=user_id)
            db.add(settings)
            db.commit()
            db.refresh(settings)
        
        if setting == "status":
            settings.notify_status_change = not settings.notify_status_change
            msg = f"Уведомления об изменении статуса: {'включены' if settings.notify_status_change else 'выключены'}"
        elif setting == "cve":
            settings.notify_new_cve = not settings.notify_new_cve
            msg = f"Уведомления о CVE: {'включены' if settings.notify_new_cve else 'выключены'}"
        elif setting == "eol":
            settings.notify_eol_warning = not settings.notify_eol_warning
            msg = f"Предупреждения EOL: {'включены' if settings.notify_eol_warning else 'выключены'}"
        elif setting == "critical":
            settings.notify_only_critical_cve = not settings.notify_only_critical_cve
            msg = f"Только критические CVE: {'включено' if settings.notify_only_critical_cve else 'выключено'}"
        else:
            await query.answer("Неизвестная настройка")
            return
        
        db.commit()
        await query.answer(msg)
        # Refresh the alerts command to show updated settings
        from bot.handlers.commands import alerts_command
        context.args = []
        await alerts_command(update, context)
    else:
        await query.answer("Неизвестная команда")
    finally:
        db.close()

