"""
VersionCheckBot - Telegram bot for monitoring software versions and CVE vulnerabilities

SPDX-License-Identifier: AGPL-3.0-or-later
Copyright (c) 2024 VersionCheckBot Contributors
"""
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


def _parse_callback(data: str, prefix: str):
    """Parse callback data using ':' as separator, stripping known prefix."""
    stripped = data[len(prefix):]
    return stripped.split(":")


@error_handler
async def callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle callback queries from inline keyboards."""
    query = update.callback_query
    if not query:
        return
    
    data = query.data
    user_id = update.effective_user.id
    
    db_gen = get_db()
    db = next(db_gen)
    try:
        vs = VersionService.shared()
        monitoring_service = MonitoringService(db, vs)
        
        if data.startswith("unsub_id:"):
            sub_id = int(_parse_callback(data, "unsub_id:")[0])
            success, message = await monitoring_service.unsubscribe(user_id, sub_id)
            await query.answer(message)
            if success:
                await query.edit_message_text("Подписка отменена.")

        elif data.startswith("unsub:"):
            parts = _parse_callback(data, "unsub:")
            if len(parts) >= 2:
                slug = parts[0]
                ver = parts[1] if parts[1] != "all" else None
                subscriptions = await monitoring_service.get_user_subscriptions(user_id)
                for sub in subscriptions:
                    if sub.product_slug == slug and sub.version == ver:
                        success, message = await monitoring_service.unsubscribe(user_id, sub.id)
                        await query.answer(message)
                        if success:
                            await query.edit_message_text("Подписка отменена.")
                        return
                await query.answer("Подписка не найдена")

        elif data.startswith("sub:"):
            parts = _parse_callback(data, "sub:")
            if len(parts) >= 2:
                slug = parts[0]
                ver = parts[1] if parts[1] != "all" else None
                success, message = await monitoring_service.subscribe(user_id, slug, ver)
                await query.answer(message)
                if success:
                    await query.edit_message_text(f"✅ Подписка на {slug}" + (f" {ver}" if ver else "") + " создана")

        elif data.startswith("detail:"):
            parts = _parse_callback(data, "detail:")
            if len(parts) >= 2:
                slug = parts[0]
                ver = parts[1] if parts[1] != "all" else None
                data_releases = await vs.releases(slug)
                if data_releases:
                    table = vs.table(slug, data_releases, highlight_version=ver)
                    await query.answer()
                    await query.edit_message_text(table, parse_mode="Markdown")
                else:
                    await query.answer("Данные не найдены")

        elif data.startswith("subs_page_"):
            page = int(data.split("_")[-1])
            context.args = [str(page)]
            await query.answer()
            from bot.handlers.commands import subscriptions_command
            await subscriptions_command(update, context)

        elif data.startswith("access_page_"):
            page = int(data.split("_")[-1])
            await query.answer()
            from bot.handlers.commands import _admin_access_list
            await _admin_access_list(update, context, sub_args=[str(page)])

        elif data.startswith("cve_page:"):
            parts = _parse_callback(data, "cve_page:")
            if len(parts) >= 3:
                slug = parts[0]
                ver = parts[1] if parts[1] != "all" else None
                page = int(parts[2])
                context.args = [slug]
                if ver:
                    context.args.append(ver)
                context.args.append(str(page))
                await query.answer()
                from bot.handlers.commands import cve_command
                await cve_command(update, context)

        elif data.startswith("fav_remove:"):
            fav_id = int(_parse_callback(data, "fav_remove:")[0])
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

        elif data.startswith("check:"):
            parts = _parse_callback(data, "check:")
            if len(parts) >= 2:
                slug = parts[0]
                ver = parts[1] if parts[1] != "all" else None
                data_releases = await vs.releases(slug)
                if data_releases:
                    table = vs.table(slug, data_releases, highlight_version=ver)
                    await query.answer()
                    await query.edit_message_text(table, parse_mode="Markdown")
                else:
                    await query.answer("Данные не найдены")

        elif data.startswith("alert_toggle:"):
            setting = _parse_callback(data, "alert_toggle:")[0]
            from bot.models import UserSettings
            
            user_settings = db.query(UserSettings).filter(UserSettings.user_id == user_id).first()
            if not user_settings:
                user_settings = UserSettings(user_id=user_id)
                db.add(user_settings)
                db.commit()
                db.refresh(user_settings)
            
            if setting == "status":
                user_settings.notify_status_change = not user_settings.notify_status_change
                msg = f"Уведомления об изменении статуса: {'включены' if user_settings.notify_status_change else 'выключены'}"
            elif setting == "cve":
                user_settings.notify_new_cve = not user_settings.notify_new_cve
                msg = f"Уведомления о CVE: {'включены' if user_settings.notify_new_cve else 'выключены'}"
            elif setting == "eol":
                user_settings.notify_eol_warning = not user_settings.notify_eol_warning
                msg = f"Предупреждения EOL: {'включены' if user_settings.notify_eol_warning else 'выключены'}"
            elif setting == "critical":
                user_settings.notify_only_critical_cve = not user_settings.notify_only_critical_cve
                msg = f"Только критические CVE: {'включено' if user_settings.notify_only_critical_cve else 'выключено'}"
            else:
                await query.answer("Неизвестная настройка")
                return
            
            db.commit()
            await query.answer(msg)
            from bot.handlers.commands import alerts_command
            context.args = []
            await alerts_command(update, context)

        elif data == "page_info":
            await query.answer()

        else:
            await query.answer("Неизвестная команда")
    finally:
        db.close()
