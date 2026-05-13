"""
VersionCheckBot - Telegram bot for monitoring software versions and CVE vulnerabilities

SPDX-License-Identifier: AGPL-3.0-or-later
Copyright (c) 2024 VersionCheckBot Contributors
"""
"""Command handlers for the bot."""
import logging
from pathlib import Path
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from functools import wraps

from bot.services.version_service import VersionService
from bot.services.monitoring_service import MonitoringService
from bot.services.cve_service import CVEService
from bot.utils.parser import parse
from bot.utils.rate_limiter import get_rate_limiter
from bot.utils.error_messages import ErrorMessages
from bot.utils.pagination import paginate_list, create_pagination_keyboard
from bot.utils.constants import DEFAULT_PAGINATION_SIZE
from bot.utils.progress import show_progress
from bot.utils.access_control import has_access, is_admin, get_bot_mode, set_bot_mode
from bot.utils.stats_collector import record_command
from bot.database.db import get_db

log = logging.getLogger(__name__)


def rate_limit_handler(func):
    """Decorator for rate limiting."""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        if update and update.effective_user:
            rate_limiter = get_rate_limiter()
            user_id = update.effective_user.id
            allowed, error_msg = await rate_limiter.is_allowed(user_id)
            if not allowed:
                if update.message:
                    await update.message.reply_text(error_msg)
                return
        return await func(update, context, *args, **kwargs)
    return wrapper


def error_handler(func):
    """Decorator for error handling — must be outermost decorator."""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        try:
            return await func(update, context, *args, **kwargs)
        except Exception as e:
            from bot.utils.exceptions import (
                BotError, APIError, DatabaseError, ValidationError,
                NotFoundError, PermissionError, RateLimitError
            )
            
            user_id = update.effective_user.id if update and update.effective_user else None
            command = func.__name__
            log.error(
                f"Error in {command}",
                extra={
                    "user_id": user_id,
                    "command": command,
                    "error_type": type(e).__name__,
                    "error_message": str(e)
                },
                exc_info=True
            )
            
            reply_target = None
            if update:
                if update.message:
                    reply_target = update.message
                elif update.callback_query and update.callback_query.message:
                    reply_target = update.callback_query.message

            if isinstance(e, (BotError, APIError, DatabaseError, ValidationError, NotFoundError, PermissionError, RateLimitError)):
                if reply_target:
                    await reply_target.reply_text(e.user_message)
            else:
                if reply_target:
                    await reply_target.reply_text(ErrorMessages.GENERIC_ERROR)
    return wrapper


def access_required(func):
    """Decorator to check if user has access to bot."""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        if not update or not update.effective_user:
            return
        
        user_id = update.effective_user.id
        
        db_gen = get_db()
        db = next(db_gen)
        try:
            user_has_access = has_access(db, user_id)
            if not user_has_access:
                if update.message:
                    await update.message.reply_text(
                        "❌ У вас нет доступа к боту.\n"
                        "Обратитесь к администратору для получения доступа."
                    )
                return
        finally:
            db.close()
        
        return await func(update, context, *args, **kwargs)
    return wrapper


def admin_only(func):
    """Decorator to check if user is admin."""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        if not update or not update.effective_user:
            return
        
        user_id = update.effective_user.id
        
        from config import settings
        if user_id in settings.ADMIN_IDS:
            return await func(update, context, *args, **kwargs)
        
        db_gen = get_db()
        db = next(db_gen)
        try:
            user_is_admin = is_admin(db, user_id)
            if not user_is_admin:
                if update.message:
                    await update.message.reply_text(ErrorMessages.ADMIN_ONLY)
                return
        finally:
            db.close()
        
        return await func(update, context, *args, **kwargs)
    return wrapper


# ────────────────────────── User Commands ──────────────────────────

@error_handler
@access_required
@rate_limit_handler
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    db_gen = get_db()
    db = next(db_gen)
    try:
        record_command(db, update.effective_user.id, "start")
    finally:
        db.close()
    
    await update.message.reply_markdown(
        "Проверяю поддерживаемость версий ПО по endoflife.date.\n"
        "*Пример:* `nodejs 22, python`\n"
        "*Inline:*  `@%s nodejs`" % context.bot.username
    )


@error_handler
@access_required
@rate_limit_handler
async def check_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /check command."""
    db_gen = get_db()
    db = next(db_gen)
    try:
        record_command(db, update.effective_user.id, "check")
    finally:
        db.close()
    
    if not context.args:
        await update.message.reply_text("Укажите продукт и версию. Пример: /check python 3.11")
        return
    
    query = " ".join(context.args)
    await respond_to_query(update, query)


@error_handler
@access_required
@rate_limit_handler
async def subscribe_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /subscribe command."""
    db_gen = get_db()
    db = next(db_gen)
    try:
        record_command(db, update.effective_user.id, "subscribe")
    finally:
        db.close()
    
    if not context.args:
        await update.message.reply_text(
            "Использование: /subscribe <продукт> [версия]\n"
            "Пример: /subscribe python 3.11"
        )
        return
    
    user_id = update.effective_user.id
    query = " ".join(context.args)
    items = parse(query)
    
    if not items:
        await update.message.reply_text("Не распознал продукт.")
        return
    
    slug, ver = items[0]
    
    db_gen = get_db()
    db = next(db_gen)
    try:
        vs = VersionService.shared()
        monitoring_service = MonitoringService(db, vs)
        
        success, message = await monitoring_service.subscribe(user_id, slug, ver)
        
        if success:
            keyboard = [[
                InlineKeyboardButton("❌ Отписаться", callback_data=f"unsub:{slug}:{ver or 'all'}")
            ]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(message, reply_markup=reply_markup)
        else:
            await update.message.reply_text(message)
    finally:
        db.close()


@error_handler
@access_required
@rate_limit_handler
async def subscriptions_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /subscriptions command."""
    user_id = update.effective_user.id
    
    db_gen = get_db()
    db = next(db_gen)
    try:
        vs = VersionService.shared()
        monitoring_service = MonitoringService(db, vs)
        
        subscriptions = await monitoring_service.get_user_subscriptions(user_id)
    
        if not subscriptions:
            reply_target = update.message or (update.callback_query and update.callback_query.message)
            if reply_target:
                await reply_target.reply_text("У вас нет активных подписок.")
            return
        
        page = int(context.args[0]) if context.args and context.args[0].isdigit() else 0
        page_items, total_pages = paginate_list(subscriptions, page, DEFAULT_PAGINATION_SIZE)
        
        lines = [f"*Ваши подписки (стр. {page + 1}/{total_pages}):*\n"]
        keyboard = []
        
        for sub in page_items:
            version_str = f" {sub.version}" if sub.version else ""
            status_emoji = "✅" if sub.last_status == "supported" else "❌"
            lines.append(f"{status_emoji} {sub.product_slug}{version_str}")
            keyboard.append([
                InlineKeyboardButton(
                    f"❌ {sub.product_slug}{version_str}",
                    callback_data=f"unsub_id:{sub.id}"
                )
            ])
        
        pagination_keyboard = create_pagination_keyboard(page, total_pages, "subs_page")
        if keyboard:
            combined_keyboard = keyboard + [pagination_keyboard.inline_keyboard[0]]
            reply_markup = InlineKeyboardMarkup(combined_keyboard)
        else:
            reply_markup = pagination_keyboard
        
        reply_target = update.message or (update.callback_query and update.callback_query.message)
        if reply_target:
            await reply_target.reply_markdown("\n".join(lines), reply_markup=reply_markup)
    finally:
        db.close()


@error_handler
@access_required
@rate_limit_handler
async def export_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /export command - export subscriptions to JSON/CSV."""
    user_id = update.effective_user.id
    format_type = context.args[0].lower() if context.args else "json"
    
    if format_type not in ["json", "csv"]:
        await update.message.reply_text("Использование: /export [json|csv]\nПо умолчанию: json")
        return
    
    db_gen = get_db()
    db = next(db_gen)
    try:
        from bot.models import Subscription
        import json
        import io
        
        subscriptions = db.query(Subscription).filter(
            Subscription.user_id == user_id,
            Subscription.is_active == True
        ).all()
        
        if not subscriptions:
            await update.message.reply_text("У вас нет активных подписок для экспорта.")
            return
        
        if format_type == "json":
            data = [{
                "product_slug": sub.product_slug,
                "version": sub.version,
                "last_status": sub.last_status,
                "created_at": sub.created_at.isoformat() if sub.created_at else None
            } for sub in subscriptions]
            
            json_str = json.dumps(data, indent=2, ensure_ascii=False)
            file_obj = io.BytesIO(json_str.encode('utf-8'))
            file_obj.name = "subscriptions.json"
            
            await update.message.reply_document(
                document=file_obj,
                caption=f"Экспортировано {len(subscriptions)} подписок"
            )
        else:
            import csv
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(["product_slug", "version", "last_status", "created_at"])
            
            for sub in subscriptions:
                writer.writerow([
                    sub.product_slug,
                    sub.version or "",
                    sub.last_status or "",
                    sub.created_at.isoformat() if sub.created_at else ""
                ])
            
            csv_str = output.getvalue()
            file_obj = io.BytesIO(csv_str.encode('utf-8'))
            file_obj.name = "subscriptions.csv"
            
            await update.message.reply_document(
                document=file_obj,
                caption=f"Экспортировано {len(subscriptions)} подписок"
            )
    finally:
        db.close()


@error_handler
@access_required
@rate_limit_handler
async def import_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /import command - import subscriptions from file."""
    if not update.message or not update.message.document:
        await update.message.reply_text(
            "Отправьте JSON или CSV файл с подписками.\n"
            'Формат JSON: [{"product_slug": "python", "version": "3.11"}, ...]\n'
            "Формат CSV: product_slug,version"
        )
        return
    
    user_id = update.effective_user.id
    doc = update.message.document
    
    if doc.mime_type not in ["application/json", "text/csv", "text/plain"]:
        await update.message.reply_text("Нужен JSON или CSV файл.")
        return
    
    try:
        file = await doc.get_file()
        content = await file.download_as_bytes()
        text = content.decode('utf-8', 'ignore')
        
        db_gen = get_db()
        db = next(db_gen)
        try:
            from bot.models import Subscription
            import json
            import csv
            import io
            
            vs = VersionService.shared()
            monitoring_service = MonitoringService(db, vs)
            
            imported = 0
            skipped = 0
            errors = []
            
            if doc.file_name and doc.file_name.endswith('.json'):
                try:
                    data = json.loads(text)
                    if not isinstance(data, list):
                        await update.message.reply_text("JSON должен содержать массив объектов.")
                        return
                    
                    for item in data:
                        if not isinstance(item, dict):
                            continue
                        product_slug = item.get("product_slug") or item.get("product")
                        version = item.get("version")
                        
                        if not product_slug:
                            skipped += 1
                            continue
                        
                        success, message = await monitoring_service.subscribe(user_id, product_slug, version)
                        if success:
                            imported += 1
                        else:
                            errors.append(f"{product_slug} {version or ''}: {message}")
                            skipped += 1
                except json.JSONDecodeError:
                    await update.message.reply_text("Ошибка парсинга JSON файла.")
                    return
            else:
                try:
                    reader = csv.DictReader(io.StringIO(text))
                    for row in reader:
                        product_slug = row.get("product_slug") or row.get("product")
                        version = row.get("version") or None
                        
                        if not product_slug:
                            skipped += 1
                            continue
                        
                        success, message = await monitoring_service.subscribe(user_id, product_slug, version)
                        if success:
                            imported += 1
                        else:
                            errors.append(f"{product_slug} {version or ''}: {message}")
                            skipped += 1
                except Exception as e:
                    await update.message.reply_text(f"Ошибка парсинга CSV файла: {e}")
                    return
            
            result_msg = f"✅ Импортировано: {imported}\n"
            if skipped > 0:
                result_msg += f"⏭ Пропущено: {skipped}\n"
            if errors and len(errors) <= 5:
                result_msg += "\nОшибки:\n" + "\n".join(errors[:5])
            elif errors:
                result_msg += f"\nОшибок: {len(errors)}"
            
            await update.message.reply_text(result_msg)
        finally:
            db.close()
    except Exception as e:
        log.error(f"Error importing subscriptions: {e}", exc_info=True)
        await update.message.reply_text("Ошибка при импорте подписок.")


@error_handler
@access_required
@rate_limit_handler
async def cve_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /cve command."""
    db_gen = get_db()
    db = next(db_gen)
    try:
        record_command(db, update.effective_user.id, "cve")
    finally:
        db.close()
    
    if not context.args:
        await update.message.reply_text(
            "Использование: /cve <продукт> [версия]\n"
            "Пример: /cve python 3.11"
        )
        return
    
    query = " ".join(context.args)
    items = parse(query)
    
    if not items:
        await update.message.reply_text("Не распознал продукт.")
        return
    
    slug, ver = items[0]
    
    await show_progress(context.bot, update.effective_chat.id, f"Поиск CVE для {slug}...")
    
    db_gen = get_db()
    db = next(db_gen)
    try:
        cve_service = CVEService(db)
        
        cves = await cve_service.search_cve(slug, ver, limit=20)
        
        if not cves:
            reply_target = update.message or (update.callback_query and update.callback_query.message)
            if reply_target:
                await reply_target.reply_text(f"CVE для {slug} не найдены.")
            return
        
        page = int(context.args[-1]) if len(context.args) > 1 and context.args[-1].isdigit() else 0
        page_cves, total_pages = paginate_list(cves, page, DEFAULT_PAGINATION_SIZE)
        
        lines = [f"*CVE для {slug}*" + (f" {ver}" if ver else "") + f" (стр. {page + 1}/{total_pages}):\n"]
        
        for cve in page_cves:
            severity_emoji = {
                "CRITICAL": "🔴",
                "HIGH": "🟠",
                "MEDIUM": "🟡",
                "LOW": "🟢"
            }.get(cve.get("severity"), "⚪")
            
            severity = cve.get("severity", "не указана")
            cve_id = cve.get("cve_id", "N/A")
            raw_desc = cve.get("description", "")
            desc = raw_desc[:100] + "..." if len(raw_desc) > 100 else raw_desc
            
            lines.append(f"{severity_emoji} *{cve_id}* ({severity})")
            if desc:
                lines.append(f"_{desc}_\n")
        
        reply_target = update.message or (update.callback_query and update.callback_query.message)
        if total_pages > 1:
            pagination_keyboard = create_pagination_keyboard(page, total_pages, f"cve_page:{slug}:{ver or 'all'}")
            if reply_target:
                await reply_target.reply_markdown("\n".join(lines), reply_markup=pagination_keyboard)
        else:
            if reply_target:
                await reply_target.reply_markdown("\n".join(lines))
    finally:
        db.close()


@error_handler
@access_required
@rate_limit_handler
async def compare_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /compare command - compare versions of products."""
    if not context.args or len(context.args) < 2:
        await update.message.reply_text(
            "Использование: /compare <продукт1> <версия1> <продукт2> <версия2>\n"
            "Пример: /compare python 3.11 python 3.12"
        )
        return
    
    query = " ".join(context.args)
    items = parse(query)
    
    if len(items) < 2:
        await update.message.reply_text("Нужно указать минимум 2 продукта для сравнения.")
        return
    
    vs = VersionService.shared()
    
    try:
        lines = ["*Сравнение версий:*\n"]
        
        for slug, ver in items[:4]:
            status = await vs.status_line(slug, ver)
            lines.append(status)
        
        await update.message.reply_markdown("\n".join(lines))
    except Exception as e:
        log.error(f"Error in compare command: {e}", exc_info=True)
        await update.message.reply_text("Ошибка при сравнении версий.")


@error_handler
@access_required
@rate_limit_handler
async def favorites_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /favorites command."""
    user_id = update.effective_user.id
    
    db_gen = get_db()
    db = next(db_gen)
    try:
        from bot.models import Favorite
        
        if context.args and context.args[0].lower() == "add" and len(context.args) >= 2:
            slug = context.args[1].lower()
            ver = context.args[2] if len(context.args) > 2 else None
            existing = db.query(Favorite).filter(
                Favorite.user_id == user_id,
                Favorite.product_slug == slug,
                Favorite.version == ver
            ).first()
            if existing:
                await update.message.reply_text(f"Продукт {slug} уже в избранном.")
                return
            fav = Favorite(user_id=user_id, product_slug=slug, version=ver)
            db.add(fav)
            db.commit()
            await update.message.reply_text(f"✅ {slug}" + (f" {ver}" if ver else "") + " добавлен в избранное.")
            return
        
        if context.args and context.args[0].lower() == "remove" and len(context.args) >= 2:
            slug = context.args[1].lower()
            ver = context.args[2] if len(context.args) > 2 else None
            fav = db.query(Favorite).filter(
                Favorite.user_id == user_id,
                Favorite.product_slug == slug,
                Favorite.version == ver
            ).first()
            if fav:
                db.delete(fav)
                db.commit()
                await update.message.reply_text(f"✅ {slug} удалён из избранного.")
            else:
                await update.message.reply_text("Не найдено в избранном.")
            return
        
        favorites = db.query(Favorite).filter(Favorite.user_id == user_id).all()
        if not favorites:
            await update.message.reply_text(
                "У вас нет избранных продуктов.\n"
                "Добавьте: /favorites add python 3.11"
            )
            return
        
        lines = ["*Избранные продукты:*\n"]
        keyboard = []
        for fav in favorites:
            ver_str = f" {fav.version}" if fav.version else ""
            lines.append(f"⭐ {fav.product_slug}{ver_str}")
            keyboard.append([
                InlineKeyboardButton(f"🔍 {fav.product_slug}{ver_str}", callback_data=f"check:{fav.product_slug}:{fav.version or 'all'}"),
                InlineKeyboardButton("❌", callback_data=f"fav_remove:{fav.id}")
            ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_markdown("\n".join(lines), reply_markup=reply_markup)
    finally:
        db.close()


@error_handler
@access_required
@rate_limit_handler
async def alerts_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /alerts command — notification settings."""
    user_id = update.effective_user.id
    
    db_gen = get_db()
    db = next(db_gen)
    try:
        from bot.models import UserSettings
        
        user_settings = db.query(UserSettings).filter(UserSettings.user_id == user_id).first()
        if not user_settings:
            user_settings = UserSettings(user_id=user_id)
            db.add(user_settings)
            db.commit()
            db.refresh(user_settings)
        
        status_icon = "✅" if user_settings.notify_status_change else "❌"
        cve_icon = "✅" if user_settings.notify_new_cve else "❌"
        eol_icon = "✅" if user_settings.notify_eol_warning else "❌"
        critical_icon = "✅" if user_settings.notify_only_critical_cve else "❌"
        
        text = (
            "*Настройки уведомлений:*\n\n"
            f"{status_icon} Изменения статуса\n"
            f"{cve_icon} Новые CVE\n"
            f"{eol_icon} Предупреждения EOL\n"
            f"{critical_icon} Только критические CVE"
        )
        
        keyboard = [
            [InlineKeyboardButton(f"{status_icon} Статус", callback_data="alert_toggle:status")],
            [InlineKeyboardButton(f"{cve_icon} CVE", callback_data="alert_toggle:cve")],
            [InlineKeyboardButton(f"{eol_icon} EOL", callback_data="alert_toggle:eol")],
            [InlineKeyboardButton(f"{critical_icon} Только крит.", callback_data="alert_toggle:critical")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        reply_target = update.message or (update.callback_query and update.callback_query.message)
        if reply_target:
            await reply_target.reply_markdown(text, reply_markup=reply_markup)
    finally:
        db.close()


@error_handler
@access_required
@rate_limit_handler
async def history_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /history command — query history."""
    user_id = update.effective_user.id
    
    db_gen = get_db()
    db = next(db_gen)
    try:
        from bot.models import QueryHistory
        from sqlalchemy import desc
        
        records = db.query(QueryHistory).filter(
            QueryHistory.user_id == user_id
        ).order_by(desc(QueryHistory.created_at)).limit(20).all()
        
        if not records:
            await update.message.reply_text("История запросов пуста.")
            return
        
        lines = ["*Последние запросы:*\n"]
        for rec in records:
            ts = rec.created_at.strftime("%d.%m %H:%M") if rec.created_at else ""
            lines.append(f"• `{rec.query_text}` ({ts})")
        
        await update.message.reply_markdown("\n".join(lines))
    finally:
        db.close()


@error_handler
@rate_limit_handler
async def health_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /health command - check bot health status."""
    import psutil
    import time
    from sqlalchemy import text
    
    health_status = {"status": "healthy", "checks": {}}
    
    try:
        db_gen = get_db()
        db = next(db_gen)
        try:
            db.execute(text("SELECT 1"))
            health_status["checks"]["database"] = {"status": "ok", "message": "Connected"}
        except Exception as e:
            health_status["checks"]["database"] = {"status": "error", "message": str(e)}
            health_status["status"] = "unhealthy"
        finally:
            db.close()
    except Exception as e:
        health_status["checks"]["database"] = {"status": "error", "message": str(e)}
        health_status["status"] = "unhealthy"
    
    try:
        vs = VersionService.shared()
        start_time = time.time()
        products = await vs.products()
        api_time = time.time() - start_time
        
        if products and len(products) > 0:
            health_status["checks"]["eol_api"] = {
                "status": "ok",
                "message": f"Connected ({len(products)} products)",
                "response_time": f"{api_time:.2f}s"
            }
        else:
            health_status["checks"]["eol_api"] = {"status": "warning", "message": "No products returned"}
    except Exception as e:
        health_status["checks"]["eol_api"] = {"status": "error", "message": str(e)}
        health_status["status"] = "unhealthy"
    
    try:
        from config import settings
        cache_dir = Path(settings.CACHE_DIR)
        if cache_dir.exists():
            cache_files = list(cache_dir.glob("*.json"))
            health_status["checks"]["cache"] = {
                "status": "ok",
                "message": f"{len(cache_files)} cache files",
            }
        else:
            health_status["checks"]["cache"] = {"status": "warning", "message": "Cache directory not found"}
    except Exception as e:
        health_status["checks"]["cache"] = {"status": "error", "message": str(e)}
    
    try:
        process = psutil.Process()
        memory_info = process.memory_info()
        memory_mb = memory_info.rss / 1024 / 1024
        health_status["checks"]["memory"] = {
            "status": "ok" if memory_mb <= 500 else "warning",
            "message": f"{memory_mb:.2f} MB",
        }
    except Exception as e:
        health_status["checks"]["memory"] = {"status": "error", "message": str(e)}
    
    status_emoji = "✅" if health_status["status"] == "healthy" else "⚠️"
    lines = [f"{status_emoji} *Health Status: {health_status['status'].upper()}*\n"]
    
    for check_name, check_data in health_status["checks"].items():
        check_emoji = "✅" if check_data["status"] == "ok" else "⚠️" if check_data["status"] == "warning" else "❌"
        line = f"{check_emoji} *{check_name.title()}*: {check_data['message']}"
        if "response_time" in check_data:
            line += f" (Response: {check_data['response_time']})"
        lines.append(line)
    
    await update.message.reply_markdown("\n".join(lines))


@error_handler
@rate_limit_handler
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command."""
    help_text = (
        "*Команды бота:*\n\n"
        "`/start` - Начать работу с ботом\n"
        "`/check <продукт> [версия]` - Проверить версию\n"
        "`/subscribe <продукт> [версия]` - Подписаться на мониторинг\n"
        "`/subscriptions` - Список подписок\n"
        "`/export [json|csv]` - Экспорт подписок\n"
        "`/import` - Импорт подписок из файла\n"
        "`/compare <продукт1> <версия1> <продукт2> <версия2>` - Сравнение версий\n"
        "`/cve <продукт> [версия]` - Поиск CVE\n"
        "`/favorites [add|remove]` - Избранные продукты\n"
        "`/alerts` - Настройки уведомлений\n"
        "`/history` - История ваших запросов\n"
        "`/health` - Проверка состояния бота\n"
        "`/stats [json|csv]` - Статистика (только для админов)\n"
        "`/admin` - Административные команды (только для админов)\n"
        "`/help` - Эта справка\n\n"
        "*Примеры:*\n"
        "`/check python 3.11`\n"
        "`/subscribe nodejs 22`\n"
        "`/compare python 3.11 python 3.12`\n"
        "`/cve python 3.11`\n\n"
        "*Inline режим:*\n"
        "Используйте `@%s <продукт>` в любом чате" % context.bot.username
    )
    await update.message.reply_markdown(help_text)


# ────────────────────────── Admin Commands ──────────────────────────

@error_handler
@admin_only
async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /stats command (admin only)."""
    db_gen = get_db()
    db = next(db_gen)
    try:
        from bot.models import User, Subscription, Notification, CVERecord, QueryHistory
        from bot.models.admin import Access, BotMode
        from bot.models.user_stats import UserStats
        from sqlalchemy import func, desc
        from datetime import datetime, timedelta
        import json as json_mod
        import io
        import csv
        
        export_format = context.args[0].lower() if context.args and context.args[0].lower() in ['json', 'csv'] else None
        
        total_users = db.query(User).count()
        active_subscriptions = db.query(Subscription).filter(Subscription.is_active == True).count()
        total_notifications = db.query(Notification).count()
        total_cves = db.query(CVERecord).count()
        
        yesterday = datetime.utcnow() - timedelta(days=1)
        recent_notifications = db.query(Notification).filter(Notification.sent_at >= yesterday).count()
        current_mode = get_bot_mode(db)
        mode_emoji = "🌐" if current_mode == "open" else "🔒"
        mode_text = "Открытый" if current_mode == "open" else "Ограниченный"
        total_with_access = db.query(Access).filter(Access.has_access == True).count()
        total_admins_count = db.query(Access).filter(Access.is_admin == True).count()
        active_users_24h = db.query(UserStats).filter(UserStats.last_activity >= yesterday).count()
        
        top_products_query = db.query(
            QueryHistory.query_text,
            func.count(QueryHistory.id).label('count')
        ).filter(
            QueryHistory.created_at >= yesterday
        ).group_by(QueryHistory.query_text).order_by(desc('count')).limit(5).all()
        
        total_commands = db.query(func.sum(UserStats.commands_count)).scalar() or 0
        
        stats_text = (
            f"*Статистика бота*\n\n"
            f"{mode_emoji} Режим: {mode_text}\n"
            f"👥 Всего пользователей: {total_users}\n"
            f"✅ С доступом: {total_with_access}\n"
            f"👑 Администраторов: {total_admins_count}\n"
            f"📋 Активных подписок: {active_subscriptions}\n"
            f"📨 Всего уведомлений: {total_notifications}\n"
            f"🔔 Уведомлений за 24ч: {recent_notifications}\n"
            f"🔒 CVE записей: {total_cves}\n"
            f"📊 Активных за 24ч: {active_users_24h}\n"
            f"⚡ Всего команд: {total_commands}"
        )
        
        if top_products_query:
            stats_text += "\n\n*Топ продуктов за 24ч:*"
            for i, (product, count) in enumerate(top_products_query[:5], 1):
                stats_text += f"\n{i}. {product[:30]} ({count}x)"
        
        if export_format:
            stats_data = {
                "mode": current_mode,
                "users": {"total": total_users, "with_access": total_with_access, "admins": total_admins_count, "active_24h": active_users_24h},
                "subscriptions": {"active": active_subscriptions},
                "notifications": {"total": total_notifications, "recent_24h": recent_notifications},
                "cve": {"total_records": total_cves},
                "commands": {"total": total_commands},
                "top_products": [{"product": product, "count": count} for product, count in top_products_query]
            }
            
            if export_format == "json":
                json_str = json_mod.dumps(stats_data, indent=2, ensure_ascii=False)
                file_obj = io.BytesIO(json_str.encode('utf-8'))
                file_obj.name = "stats.json"
                await update.message.reply_document(document=file_obj, caption="Статистика бота (JSON)")
            else:
                output = io.StringIO()
                writer = csv.writer(output)
                writer.writerow(["Metric", "Value"])
                writer.writerow(["Mode", current_mode])
                writer.writerow(["Total Users", total_users])
                writer.writerow(["Active Subscriptions", active_subscriptions])
                writer.writerow(["Total Notifications", total_notifications])
                writer.writerow(["CVE Records", total_cves])
                writer.writerow(["Active Users 24h", active_users_24h])
                writer.writerow(["Total Commands", total_commands])
                csv_str = output.getvalue()
                file_obj = io.BytesIO(csv_str.encode('utf-8'))
                file_obj.name = "stats.csv"
                await update.message.reply_document(document=file_obj, caption="Статистика бота (CSV)")
        else:
            await update.message.reply_markdown(stats_text)
    finally:
        db.close()


@error_handler
@admin_only
async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /admin command."""
    if not context.args:
        db_gen = get_db()
        db = next(db_gen)
        try:
            current_mode = get_bot_mode(db)
            mode_text = "Открытый" if current_mode == "open" else "Ограниченный"
            mode_emoji = "🌐" if current_mode == "open" else "🔒"
        finally:
            db.close()
        
        help_text = (
            "*Административные команды:*\n\n"
            f"{mode_emoji} Текущий режим: {mode_text}\n\n"
            "`/admin mode` - Переключить режим (открытый/ограниченный)\n"
            "`/admin cache_clear` - Очистить кэш\n"
            "`/admin users` - Список пользователей\n"
            "`/admin access` - Список пользователей с доступом\n"
            "`/admin grant <user_id>` - Выдать доступ\n"
            "`/admin revoke <user_id>` - Отозвать доступ\n"
            "`/admin make_admin <user_id>` - Сделать администратором\n"
            "`/admin remove_admin <user_id>` - Убрать администратора\n"
            "`/admin broadcast <сообщение>` - Рассылка всем пользователям\n"
            "`/admin backup` - Создать backup базы данных\n"
            "`/stats` - Статистика бота"
        )
        await update.message.reply_markdown(help_text)
        return
    
    subcommand = context.args[0].lower()
    sub_args = context.args[1:]
    
    if subcommand == "mode":
        await _admin_mode(update, context)
    elif subcommand == "cache_clear":
        await _admin_cache_clear(update, context)
    elif subcommand == "users":
        await _admin_users(update, context)
    elif subcommand == "access":
        await _admin_access_list(update, context, sub_args)
    elif subcommand == "grant":
        await _admin_grant_access(update, context, sub_args)
    elif subcommand == "revoke":
        await _admin_revoke_access(update, context, sub_args)
    elif subcommand == "make_admin":
        await _admin_make_admin(update, context, sub_args)
    elif subcommand == "remove_admin":
        await _admin_remove_admin(update, context, sub_args)
    elif subcommand == "broadcast":
        await _admin_broadcast(update, context, sub_args)
    elif subcommand in ("backup", "export_db"):
        await _admin_backup(update, context)
    else:
        await update.message.reply_text(f"Неизвестная команда: {subcommand}")


async def _admin_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db_gen = get_db()
    db = next(db_gen)
    try:
        current = get_bot_mode(db)
        new_mode = "restricted" if current == "open" else "open"
        set_bot_mode(db, new_mode, update.effective_user.id)
        emoji = "🌐" if new_mode == "open" else "🔒"
        label = "Открытый" if new_mode == "open" else "Ограниченный"
        await update.message.reply_text(f"{emoji} Режим изменён на: {label}")
    finally:
        db.close()


async def _admin_cache_clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from bot.services.version_service import _cache as eol_cache
    from bot.services.cve_service import _cache as cve_cache
    await eol_cache.clear()
    await cve_cache.clear()
    await update.message.reply_text("✅ Кэш очищен (EOL + CVE).")


async def _admin_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db_gen = get_db()
    db = next(db_gen)
    try:
        from bot.models import User
        users = db.query(User).order_by(User.created_at.desc()).limit(DEFAULT_PAGINATION_SIZE).all()
        if not users:
            await update.message.reply_text("Пользователей не найдено.")
            return
        lines = [f"*Последние {len(users)} пользователей:*\n"]
        for user in users:
            username = user.username or "без username"
            lines.append(f"• {username} (ID: {user.user_id})")
        await update.message.reply_markdown("\n".join(lines))
    finally:
        db.close()


async def _admin_access_list(update: Update, context: ContextTypes.DEFAULT_TYPE, sub_args=None):
    db_gen = get_db()
    db = next(db_gen)
    try:
        from bot.models.admin import Access
        page = int(sub_args[0]) if sub_args and sub_args[0].isdigit() else 0
        all_access = db.query(Access).filter(Access.has_access == True).all()
        if not all_access:
            reply_target = update.message or (update.callback_query and update.callback_query.message)
            if reply_target:
                await reply_target.reply_text("Список доступа пуст.")
            return
        page_items, total_pages = paginate_list(all_access, page, DEFAULT_PAGINATION_SIZE)
        lines = [f"*Пользователи с доступом (стр. {page + 1}/{total_pages}):*\n"]
        for acc in page_items:
            role = "👑 Админ" if acc.is_admin else "👤 Пользователь"
            lines.append(f"• ID: {acc.user_id} — {role}")
        pagination_keyboard = create_pagination_keyboard(page, total_pages, "access_page")
        reply_target = update.message or (update.callback_query and update.callback_query.message)
        if reply_target:
            await reply_target.reply_markdown("\n".join(lines), reply_markup=pagination_keyboard)
    finally:
        db.close()


async def _admin_grant_access(update: Update, context: ContextTypes.DEFAULT_TYPE, sub_args):
    if not sub_args:
        await update.message.reply_text("Использование: /admin grant <user_id>")
        return
    try:
        target_id = int(sub_args[0])
    except ValueError:
        await update.message.reply_text("user_id должен быть числом.")
        return
    db_gen = get_db()
    db = next(db_gen)
    try:
        from bot.models.admin import Access
        existing = db.query(Access).filter(Access.user_id == target_id).first()
        if existing:
            existing.has_access = True
            existing.granted_by = update.effective_user.id
        else:
            acc = Access(user_id=target_id, has_access=True, granted_by=update.effective_user.id)
            db.add(acc)
        db.commit()
        await update.message.reply_text(f"✅ Доступ выдан пользователю {target_id}.")
    finally:
        db.close()


async def _admin_revoke_access(update: Update, context: ContextTypes.DEFAULT_TYPE, sub_args):
    if not sub_args:
        await update.message.reply_text("Использование: /admin revoke <user_id>")
        return
    try:
        target_id = int(sub_args[0])
    except ValueError:
        await update.message.reply_text("user_id должен быть числом.")
        return
    db_gen = get_db()
    db = next(db_gen)
    try:
        from bot.models.admin import Access
        existing = db.query(Access).filter(Access.user_id == target_id).first()
        if existing:
            existing.has_access = False
            db.commit()
            await update.message.reply_text(f"✅ Доступ отозван у пользователя {target_id}.")
        else:
            await update.message.reply_text("Пользователь не найден в списке доступа.")
    finally:
        db.close()


async def _admin_make_admin(update: Update, context: ContextTypes.DEFAULT_TYPE, sub_args):
    if not sub_args:
        await update.message.reply_text("Использование: /admin make_admin <user_id>")
        return
    try:
        target_id = int(sub_args[0])
    except ValueError:
        await update.message.reply_text("user_id должен быть числом.")
        return
    db_gen = get_db()
    db = next(db_gen)
    try:
        from bot.models.admin import Access
        existing = db.query(Access).filter(Access.user_id == target_id).first()
        if existing:
            existing.is_admin = True
            existing.has_access = True
        else:
            acc = Access(user_id=target_id, has_access=True, is_admin=True, granted_by=update.effective_user.id)
            db.add(acc)
        db.commit()
        await update.message.reply_text(f"✅ Пользователь {target_id} назначен администратором.")
    finally:
        db.close()


async def _admin_remove_admin(update: Update, context: ContextTypes.DEFAULT_TYPE, sub_args):
    if not sub_args:
        await update.message.reply_text("Использование: /admin remove_admin <user_id>")
        return
    try:
        target_id = int(sub_args[0])
    except ValueError:
        await update.message.reply_text("user_id должен быть числом.")
        return
    db_gen = get_db()
    db = next(db_gen)
    try:
        from bot.models.admin import Access
        existing = db.query(Access).filter(Access.user_id == target_id).first()
        if existing:
            existing.is_admin = False
            db.commit()
            await update.message.reply_text(f"✅ Пользователь {target_id} больше не администратор.")
        else:
            await update.message.reply_text("Пользователь не найден.")
    finally:
        db.close()


async def _admin_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE, sub_args):
    if not sub_args:
        await update.message.reply_text("Использование: /admin broadcast <сообщение>")
        return
    message = " ".join(sub_args)
    db_gen = get_db()
    db = next(db_gen)
    try:
        from bot.models import User
        users = db.query(User).filter(User.is_active == True).all()
        sent = 0
        failed = 0
        await update.message.reply_text(f"Отправка сообщения {len(users)} пользователям...")
        for user in users:
            try:
                await context.bot.send_message(chat_id=user.user_id, text=message)
                sent += 1
            except Exception as e:
                log.warning(f"Failed to send broadcast to {user.user_id}: {e}")
                failed += 1
        await update.message.reply_text(f"✅ Рассылка завершена.\nОтправлено: {sent}\nОшибок: {failed}")
    finally:
        db.close()


async def _admin_backup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    import shutil
    import io
    from config import settings
    db_url = settings.DATABASE_URL
    if not db_url.startswith("sqlite:///"):
        await update.message.reply_text("Backup доступен только для SQLite базы данных.")
        return
    db_path = db_url.replace("sqlite:///", "")
    if not Path(db_path).is_absolute():
        db_path = str(Path(db_path).resolve())
    if not Path(db_path).exists():
        await update.message.reply_text("Файл базы данных не найден.")
        return
    try:
        with open(db_path, "rb") as f:
            file_obj = io.BytesIO(f.read())
        file_obj.name = "bot_backup.db"
        await update.message.reply_document(document=file_obj, caption="Backup базы данных")
    except Exception as e:
        log.error(f"Error creating backup: {e}", exc_info=True)
        await update.message.reply_text(f"Ошибка при создании backup: {e}")


# ────────────────────────── Shared Helpers ──────────────────────────

async def respond_to_query(update: Update, query: str, version_service: VersionService = None):
    """Respond to a product/version query."""
    if version_service is None:
        version_service = VersionService.shared()
    
    if update and update.effective_user:
        try:
            db_gen = get_db()
            db = next(db_gen)
            try:
                from bot.models import QueryHistory
                history = QueryHistory(
                    user_id=update.effective_user.id,
                    query_text=query,
                    query_type="check"
                )
                db.add(history)
                db.commit()
            except Exception as e:
                log.warning(f"Failed to save query history: {e}")
                db.rollback()
            finally:
                db.close()
        except Exception as e:
            log.warning(f"Error saving history: {e}")
    
    try:
        items = parse(query)
        if not items:
            await update.message.reply_text("Не распознал продукты.")
            return
        
        if len(items) == 1:
            slug, ver = items[0]
            data = await version_service.releases(slug)
            if data:
                table = version_service.table(slug, data, highlight_version=ver)
                await update.message.reply_markdown(table)
                return
        
        import asyncio
        from config import settings
        
        sem = asyncio.Semaphore(settings.MAX_PARALLEL)
        
        async def job(s, v):
            async with sem:
                try:
                    return await version_service.status_line(s, v)
                except Exception as e:
                    log.error(f"Error processing {s} {v}: {e}")
                    return f"❌ {s}: ошибка при получении данных"
        
        lines = await asyncio.gather(*(job(s, v) for s, v in items), return_exceptions=True)
        valid_lines = [line if not isinstance(line, Exception) else f"Ошибка: {line}" for line in lines]
        await update.message.reply_text("\n".join(valid_lines))
    except Exception as e:
        log.error(f"Error in respond_to_query: {e}", exc_info=True)
        await update.message.reply_text("Произошла ошибка при обработке запроса.")
