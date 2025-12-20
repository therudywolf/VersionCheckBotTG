"""Inline query handlers."""
import logging
from telegram import InlineQueryResultArticle, InputTextMessageContent, Update
from telegram.ext import ContextTypes
from functools import wraps

from bot.services.version_service import VersionService
from bot.utils.parser import parse
from bot.utils.fuzzy import sugg

log = logging.getLogger(__name__)


def error_handler(func):
    """Decorator for error handling in handlers."""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        try:
            return await func(update, context, *args, **kwargs)
        except Exception as e:
            log.error(f"Error in {func.__name__}: {e}", exc_info=True)
            if update and update.inline_query:
                await update.inline_query.answer([], cache_time=0)
    return wrapper


@error_handler
async def inline_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle inline queries."""
    query = update.inline_query.query.strip()
    if not query:
        return
    
    version_service = VersionService()
    
    try:
        parsed = parse(query)
        if parsed:
            slug, ver = parsed[0]
        else:
            slug, ver = query, None
        
        choices = await version_service.products()
        best = sugg(slug, choices)
        results = []
        
        for idx, s in enumerate(best):
            try:
                status = await version_service.status_line(s, ver)
                results.append(
                    InlineQueryResultArticle(
                        id=str(idx),
                        title=status.split('→')[0].strip('✅❌ '),
                        description=status,
                        input_message_content=InputTextMessageContent(status)
                    )
                )
            except Exception as e:
                log.warning(f"Error processing {s} in inline query: {e}")
                continue
        
        await update.inline_query.answer(results, cache_time=120)
    except Exception as e:
        log.error(f"Error in inline query: {e}", exc_info=True)
        await update.inline_query.answer([], cache_time=0)

