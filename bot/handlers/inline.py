"""
VersionCheckBot - Telegram bot for monitoring software versions and CVE vulnerabilities

SPDX-License-Identifier: AGPL-3.0-or-later
Copyright (c) 2024 VersionCheckBot Contributors
"""
"""Inline query handlers."""
import logging
from typing import Any, List
from telegram import (
    InlineQueryResultArticle,
    InputTextMessageContent,
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)
from telegram.ext import ContextTypes
from functools import wraps

from bot.services.version_service import VersionService
from bot.utils.parser import parse
from bot.utils.fuzzy import sugg
from bot.utils.constants import EMOJI_ARROW, EMOJI_CHECK, EMOJI_CROSS

log = logging.getLogger(__name__)


def error_handler(func):
    """Decorator for error handling in handlers."""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args: Any, **kwargs: Any) -> Any:
        try:
            return await func(update, context, *args, **kwargs)
        except Exception as e:
            log.error(f"Error in {func.__name__}: {e}", exc_info=True)
            if update and update.inline_query:
                await update.inline_query.answer([], cache_time=0)
    return wrapper


@error_handler
async def inline_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle inline queries."""
    from bot.database.db import get_db
    from bot.utils.access_control import has_access
    db_gen = get_db()
    db = next(db_gen)
    try:
        if not has_access(db, update.effective_user.id):
            await update.inline_query.answer([], cache_time=0)
            return
    finally:
        db.close()
    
    query = update.inline_query.query.strip()
    if not query:
        return
    
    vs = VersionService.shared()
    
    try:
        parsed = parse(query)
        if parsed:
            slug, ver = parsed[0]
        else:
            slug, ver = query, None
        
        choices = await vs.products()
        best = sugg(slug, choices)
        results = []
        
        for idx, s in enumerate(best[:10]):
            try:
                status = await vs.status_line(s, ver)
                
                releases = await vs.releases(s)
                detail_text = status
                if releases and len(releases) > 0:
                    latest_release = releases[0]
                    latest = vs._release_latest(latest_release)
                    eol = vs._release_eol(latest_release) or "N/A"
                    detail_text = f"{status}\nПоследний: {latest} | EOL: {eol}"
                
                keyboard = [
                    [
                        InlineKeyboardButton("📋 Подписаться", callback_data=f"sub:{s}:{ver or 'all'}"),
                        InlineKeyboardButton("🔍 Детали", callback_data=f"detail:{s}:{ver or 'all'}")
                    ]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                title = status.split(EMOJI_ARROW)[0].strip(f'{EMOJI_CHECK}{EMOJI_CROSS} ')
                if len(title) > 50:
                    title = title[:47] + "..."
                
                results.append(
                    InlineQueryResultArticle(
                        id=f"{s}_{idx}",
                        title=title,
                        description=detail_text[:100] if len(detail_text) > 100 else detail_text,
                        input_message_content=InputTextMessageContent(status),
                        reply_markup=reply_markup
                    )
                )
            except Exception as e:
                log.warning(f"Error processing {s} in inline query: {e}")
                continue
        
        await update.inline_query.answer(results, cache_time=120)
    except Exception as e:
        log.error(f"Error in inline query: {e}", exc_info=True)
        await update.inline_query.answer([], cache_time=0)
