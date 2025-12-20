"""Command handlers for the bot."""
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from functools import wraps

from bot.services.version_service import VersionService
from bot.services.monitoring_service import MonitoringService
from bot.services.cve_service import CVEService
from bot.utils.parser import parse
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
            if update and update.message:
                await update.message.reply_text(
                    "Произошла ошибка при обработке запроса. Попробуйте позже."
                )
    return wrapper


@error_handler
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    await update.message.reply_markdown(
        "Проверяю поддерживаемость версий ПО по endoflife.date.\n"
        "*Пример:* `nodejs 22, python`\n"
        "*Inline:*  `@%s nodejs`" % context.bot.username
    )


@error_handler
async def check_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /check command."""
    if not context.args:
        await update.message.reply_text("Укажите продукт и версию. Пример: /check python 3.11")
        return
    
    query = " ".join(context.args)
    await respond_to_query(update, query)


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
        
        # Format subscriptions list
        lines = ["*Ваши подписки:*\n"]
        keyboard = []
        
        for sub in subscriptions:
            version_str = f" {sub.version}" if sub.version else ""
            status_emoji = "✅" if sub.last_status == "supported" else "❌"
            lines.append(f"{status_emoji} {sub.product_slug}{version_str}")
            keyboard.append([
                InlineKeyboardButton(
                    f"❌ {sub.product_slug}{version_str}",
                    callback_data=f"unsub_id_{sub.id}"
                )
            ])
        
        reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None
        await update.message.reply_markdown("\n".join(lines), reply_markup=reply_markup)
    finally:
        db.close()


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
    
    # Get database session
    db_gen = get_db()
    db = next(db_gen)
    try:
        cve_service = CVEService(db)
        
        await update.message.reply_text(f"Поиск CVE для {slug}...")
        
        cves = await cve_service.search_cve(slug, ver, limit=5)
        
        if not cves:
            await update.message.reply_text(f"CVE для {slug} не найдены.")
            return
        
        # Format CVE list
        lines = [f"*CVE для {slug}*" + (f" {ver}" if ver else "") + ":\n"]
        
        for cve in cves[:5]:
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
        
        await update.message.reply_markdown("\n".join(lines))
    finally:
        db.close()


@error_handler
async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /stats command (admin only)."""
    user_id = update.effective_user.id
    
    # Check if user is admin
    if user_id not in settings.ADMIN_IDS:
        await update.message.reply_text("Эта команда доступна только администраторам.")
        return
    
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


@error_handler
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command."""
    help_text = (
        "*Команды бота:*\n\n"
        "`/start` - Начать работу с ботом\n"
        "`/check <продукт> [версия]` - Проверить версию\n"
        "`/subscribe <продукт> [версия]` - Подписаться на мониторинг\n"
        "`/subscriptions` - Список подписок\n"
        "`/cve <продукт> [версия]` - Поиск CVE\n"
        "`/stats` - Статистика (только для админов)\n"
        "`/help` - Эта справка\n\n"
        "*Примеры:*\n"
        "`/check python 3.11`\n"
        "`/subscribe nodejs 22`\n"
        "`/cve python 3.11`\n\n"
        "*Inline режим:*\n"
        "Используйте `@%s <продукт>` в любом чате" % context.bot.username
    )
    
    await update.message.reply_markdown(help_text)


async def respond_to_query(update: Update, query: str, version_service: VersionService = None):
    """Respond to a product/version query."""
    if version_service is None:
        version_service = VersionService()
    
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

