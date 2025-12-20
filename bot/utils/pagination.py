"""Pagination utilities for large lists."""
from typing import List, Tuple, Any
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from bot.utils.constants import DEFAULT_PAGINATION_SIZE


def create_pagination_keyboard(
    current_page: int,
    total_pages: int,
    prefix: str = "page"
) -> InlineKeyboardMarkup:
    """
    Create pagination keyboard.
    
    Args:
        current_page: Current page number (0-indexed)
        total_pages: Total number of pages
        prefix: Callback data prefix
        
    Returns:
        InlineKeyboardMarkup with pagination buttons
    """
    buttons = []
    
    # Previous button
    if current_page > 0:
        buttons.append(InlineKeyboardButton("◀ Назад", callback_data=f"{prefix}_{current_page - 1}"))
    
    # Page info
    buttons.append(InlineKeyboardButton(f"{current_page + 1}/{total_pages}", callback_data="page_info"))
    
    # Next button
    if current_page < total_pages - 1:
        buttons.append(InlineKeyboardButton("Вперед ▶", callback_data=f"{prefix}_{current_page + 1}"))
    
    return InlineKeyboardMarkup([buttons])


def paginate_list(
    items: List[Any],
    page: int = 0,
    page_size: int = DEFAULT_PAGINATION_SIZE
) -> Tuple[List[Any], int]:
    """
    Paginate a list of items.
    
    Args:
        items: List of items to paginate
        page: Page number (0-indexed)
        page_size: Number of items per page
        
    Returns:
        Tuple of (items_for_page, total_pages)
    """
    total_pages = (len(items) + page_size - 1) // page_size if items else 1
    page = max(0, min(page, total_pages - 1))
    
    start = page * page_size
    end = start + page_size
    
    return items[start:end], total_pages

