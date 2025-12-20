"""Command handlers for the bot."""
import logging
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
    """Decorator for error handling in handlers."""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        try:
            return await func(update, context, *args, **kwargs)
        except Exception as e:
            log.error(f"Error in {func.__name__}: {e}", exc_info=True)
            if update and update.message:
                await update.message.reply_text(ErrorMessages.GENERIC_ERROR)
    return wrapper


@rate_limit_handler
@error_handler
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    await update.message.reply_markdown(
        "Проверяю поддерживаемость версий ПО по endoflife.date.\n"
        "*Пример:* `nodejs 22, python`\n"
        "*Inline:*  `@%s nodejs`" % context.bot.username
    )


@rate_limit_handler
@error_handler
async def check_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /check command."""
    if not context.args:
        await update.message.reply_text("Укажите продукт и версию. Пример: /check python 3.11")
        return
    
    query = " ".join(context.args)
    await respond_to_query(update, query)


@rate_limit_handler
@error_handler
async def subscribe_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /subscribe command."""
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
    
    # Get database session
    db_gen = get_db()
    db = next(db_gen)
    try:
        version_service = VersionService()
        monitoring_service = MonitoringService(db, version_service)
        
        success, message = await monitoring_service.subscribe(user_id, slug, ver)
        
        if success:
            # Add inline keyboard with unsubscribe option
            keyboard = [[
                InlineKeyboardButton("❌ Отписаться", callback_data=f"unsub_{slug}_{ver or 'all'}")
            ]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(message, reply_markup=reply_markup)
        else:
            await update.message.reply_text(message)
    finally:
        db.close()


@rate_limit_handler
@error_handler
async def subscriptions_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /subscriptions command."""
    user_id = update.effective_user.id
    
    # Get database session
    db_gen = get_db()
    db = next(db_gen)
    try:
        version_service = VersionService()
        monitoring_service = MonitoringService(db, version_service)
        
        subscriptions = await monitoring_service.get_user_subscriptions(user_id)
    
        if not subscriptions:
            await update.message.reply_text("У вас нет активных подписок.")
            return
        
        # Paginate subscriptions
        page = int(context.args[0]) if context.args and context.args[0].isdigit() else 0
        page_items, total_pages = paginate_list(subscriptions, page, DEFAULT_PAGINATION_SIZE)
        
        # Format subscriptions list
        lines = [f"*Ваши подписки (стр. {page + 1}/{total_pages}):*\n"]
        keyboard = []
        
        for sub in page_items:
            version_str = f" {sub.version}" if sub.version else ""
            status_emoji = "✅" if sub.last_status == "supported" else "❌"
            lines.append(f"{status_emoji} {sub.product_slug}{version_str}")
            keyboard.append([
                InlineKeyboardButton(
                    f"❌ {sub.product_slug}{version_str}",
                    callback_data=f"unsub_id_{sub.id}"
                )
            ])
        
        # Add pagination buttons
        pagination_keyboard = create_pagination_keyboard(page, total_pages, "subs_page")
        if keyboard:
            # Combine unsubscribe buttons with pagination
            combined_keyboard = keyboard + [pagination_keyboard.inline_keyboard[0]]
            reply_markup = InlineKeyboardMarkup(combined_keyboard)
        else:
            reply_markup = pagination_keyboard
        
        await update.message.reply_markdown("\n".join(lines), reply_markup=reply_markup)
    finally:
        db.close()


@rate_limit_handler
@error_handler
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
        else:  # CSV
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


@rate_limit_handler
@error_handler
async def import_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /import command - import subscriptions from file."""
    if not update.message or not update.message.document:
        await update.message.reply_text(
            "Отправьте JSON или CSV файл с подписками.\n"
            "Формат JSON: [{\"product_slug\": \"python\", \"version\": \"3.11\"}, ...]\n"
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
            from bot.services.monitoring_service import MonitoringService
            from bot.services.version_service import VersionService
            import json
            import csv
            import io
            
            version_service = VersionService()
            monitoring_service = MonitoringService(db, version_service)
            
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
            else:  # CSV
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


@rate_limit_handler
@error_handler
async def cve_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /cve command."""
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
    
    # Show progress
    await show_progress(context.bot, update.effective_chat.id, f"Поиск CVE для {slug}...")
    
    # Get database session
    db_gen = get_db()
    db = next(db_gen)
    try:
        cve_service = CVEService(db)
        
        cves = await cve_service.search_cve(slug, ver, limit=20)  # Get more for pagination
        
        if not cves:
            await update.message.reply_text(f"CVE для {slug} не найдены.")
            return
        
        # Paginate CVE results
        page = int(context.args[1]) if len(context.args) > 1 and context.args[1].isdigit() else 0
        page_cves, total_pages = paginate_list(cves, page, DEFAULT_PAGINATION_SIZE)
        
        # Format CVE list
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
            desc = cve.get("description", "")[:100] + "..." if len(cve.get("description", "")) > 100 else cve.get("description", "")
            
            lines.append(f"{severity_emoji} *{cve_id}* ({severity})")
            if desc:
                lines.append(f"_{desc}_\n")
        
        # Add pagination if needed
        if total_pages > 1:
            pagination_keyboard = create_pagination_keyboard(page, total_pages, f"cve_page_{slug}_{ver or 'all'}")
            await update.message.reply_markdown("\n".join(lines), reply_markup=pagination_keyboard)
        else:
            await update.message.reply_markdown("\n".join(lines))
    finally:
        db.close()


def admin_only(func):
    """Decorator to check if user is admin."""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = update.effective_user.id
        if user_id not in settings.ADMIN_IDS:
            await update.message.reply_text(ErrorMessages.ADMIN_ONLY)
            return
        return await func(update, context, *args, **kwargs)
    return wrapper


@admin_only
@error_handler
async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /stats command (admin only)."""
    
    # Get database session
    db_gen = get_db()
    db = next(db_gen)
    try:
        from bot.models import User, Subscription, Notification, CVERecord
        
        # Get statistics
        total_users = db.query(User).count()
        active_subscriptions = db.query(Subscription).filter(Subscription.is_active == True).count()
        total_notifications = db.query(Notification).count()
        total_cves = db.query(CVERecord).count()
        
        # Recent activity (last 24 hours)
        from datetime import datetime, timedelta
        yesterday = datetime.utcnow() - timedelta(days=1)
        recent_notifications = db.query(Notification).filter(
            Notification.sent_at >= yesterday
        ).count()
        
        stats_text = (
            f"*Статистика бота*\n\n"
            f"👥 Пользователей: {total_users}\n"
            f"📋 Активных подписок: {active_subscriptions}\n"
            f"📨 Всего уведомлений: {total_notifications}\n"
            f"🔔 Уведомлений за 24ч: {recent_notifications}\n"
            f"🔒 CVE записей: {total_cves}"
        )
        
        await update.message.reply_markdown(stats_text)
    finally:
        db.close()


@admin_only
@error_handler
async def admin_cache_clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /admin cache_clear command."""
    from bot.utils.cache import TTLCache
    cache = TTLCache()
    await cache.clear()
    await update.message.reply_text("✅ Кэш очищен.")


@admin_only
@error_handler
async def admin_users_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /admin users command."""
    db_gen = get_db()
    db = next(db_gen)
    try:
        from bot.models import User
        from bot.utils.constants import DEFAULT_PAGINATION_SIZE
        
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


@admin_only
@error_handler
async def admin_broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /admin broadcast command."""
    if not context.args:
        await update.message.reply_text("Использование: /admin broadcast <сообщение>")
        return
    
    message = " ".join(context.args)
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
        
        await update.message.reply_text(
            f"✅ Рассылка завершена.\n"
            f"Отправлено: {sent}\n"
            f"Ошибок: {failed}"
        )
    finally:
        db.close()


@admin_only
@error_handler
async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /admin command."""
    if not context.args:
        help_text = (
            "*Административные команды:*\n\n"
            "`/admin cache_clear` - Очистить кэш\n"
            "`/admin users` - Список пользователей\n"
            "`/admin broadcast <сообщение>` - Рассылка всем пользователям\n"
            "`/admin export_db` - Экспорт базы данных\n"
            "`/stats` - Статистика бота"
        )
        await update.message.reply_markdown(help_text)
        return
    
    subcommand = context.args[0].lower()
    
    if subcommand == "cache_clear":
        await admin_cache_clear_command(update, context)
    elif subcommand == "users":
        await admin_users_command(update, context)
    elif subcommand == "broadcast":
        await admin_broadcast_command(update, context)
    elif subcommand == "export_db":
        await update.message.reply_text("Экспорт БД в разработке.")
    else:
        await update.message.reply_text(f"Неизвестная команда: {subcommand}")


@rate_limit_handler
@error_handler
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
    
    version_service = VersionService()
    
    try:
        lines = ["*Сравнение версий:*\n"]
        
        for slug, ver in items[:4]:  # Limit to 4 for readability
            status = await version_service.status_line(slug, ver)
            lines.append(status)
        
        await update.message.reply_text("\n".join(lines))
    except Exception as e:
        log.error(f"Error in compare command: {e}", exc_info=True)
        await update.message.reply_text("Ошибка при сравнении версий.")


@rate_limit_handler
@error_handler
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
        "`/stats` - Статистика (только для админов)\n"
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


async def respond_to_query(update: Update, query: str, version_service: VersionService = None):
    """Respond to a product/version query."""
    if version_service is None:
        version_service = VersionService()
    
    # Save to history
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
        # Filter out exceptions
        valid_lines = [line if not isinstance(line, Exception) else f"Ошибка: {line}" for line in lines]
        await update.message.reply_text("\n".join(valid_lines))
    except Exception as e:
        log.error(f"Error in respond_to_query: {e}", exc_info=True)
        await update.message.reply_text("Произошла ошибка при обработке запроса.")

