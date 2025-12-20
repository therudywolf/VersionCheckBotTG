"""Message handlers for text and file messages."""
import logging
from telegram import Update
from telegram.ext import ContextTypes
from functools import wraps

from bot.services.version_service import VersionService
from bot.utils.parser import parse
from bot.handlers.commands import respond_to_query

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
                    "Произошла ошибка при обработке сообщения. Попробуйте позже."
                )
    return wrapper


@error_handler
async def text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle text messages."""
    if not update.message or not update.message.text:
        return
    
    await respond_to_query(update, update.message.text)


@error_handler
async def file_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle file messages (txt files)."""
    if not update.message or not update.message.document:
        return
    
    doc = update.message.document
    if doc.mime_type != "text/plain":
        from bot.utils.error_messages import ErrorMessages
        await update.message.reply_text(ErrorMessages.FILE_INVALID_TYPE)
        return
    
    try:
        file = await doc.get_file()
        content = await file.download_as_bytes()
        text = content.decode('utf-8', 'ignore')
        if not text.strip():
            from bot.utils.error_messages import ErrorMessages
            await update.message.reply_text(ErrorMessages.FILE_EMPTY)
            return
        await respond_to_query(update, text)
    except Exception as e:
        log.error(f"Error processing file: {e}", exc_info=True)
        from bot.utils.error_messages import ErrorMessages
        await update.message.reply_text(ErrorMessages.FILE_READ_ERROR)

