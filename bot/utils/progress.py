"""
VersionCheckBot - Telegram bot for monitoring software versions and CVE vulnerabilities

SPDX-License-Identifier: AGPL-3.0-or-later
Copyright (c) 2024 VersionCheckBot Contributors
"""
"""Progress indicators for long operations."""
import asyncio
from typing import Optional
from telegram import Update, Bot
from telegram.constants import ChatAction


async def show_progress(bot: Bot, chat_id: int, message: str = "Обработка..."):
    """
    Show typing indicator.
    
    Args:
        bot: Telegram bot instance
        chat_id: Chat ID
        message: Optional message to send
    """
    await bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)


async def send_progress_message(bot: Bot, chat_id: int, message: str) -> Optional[int]:
    """
    Send progress message and return message ID.
    
    Args:
        bot: Telegram bot instance
        chat_id: Chat ID
        message: Progress message
        
    Returns:
        Message ID or None
    """
    try:
        sent = await bot.send_message(chat_id=chat_id, text=message)
        return sent.message_id
    except Exception:
        return None


async def update_progress_message(bot: Bot, chat_id: int, message_id: int, message: str):
    """
    Update progress message.
    
    Args:
        bot: Telegram bot instance
        chat_id: Chat ID
        message_id: Message ID to update
        message: New message text
    """
    try:
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=message
        )
    except Exception:
        pass  # Message might be deleted or unchanged

