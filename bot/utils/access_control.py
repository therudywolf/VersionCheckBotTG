"""Access control utilities."""
from typing import Optional
from sqlalchemy.orm import Session

from bot.models.admin import Access, BotMode


def has_access(db: Session, user_id: int) -> bool:
    """
    Check if user has access to bot.
    
    Args:
        db: Database session
        user_id: Telegram user ID
        
    Returns:
        True if user has access, False otherwise
    """
    # Check bot mode
    bot_mode = db.query(BotMode).first()
    if not bot_mode:
        # Default to open mode
        return True
    
    # If open mode, everyone has access
    if bot_mode.mode == "open":
        return True
    
    # If restricted mode, check access list
    access = db.query(Access).filter(
        Access.user_id == user_id,
        Access.has_access == True
    ).first()
    
    return access is not None


def is_admin(db: Session, user_id: int) -> bool:
    """
    Check if user is admin.
    
    Args:
        db: Database session
        user_id: Telegram user ID
        
    Returns:
        True if admin, False otherwise
    """
    access = db.query(Access).filter(
        Access.user_id == user_id,
        Access.is_admin == True
    ).first()
    
    return access is not None


def get_bot_mode(db: Session) -> str:
    """
    Get current bot mode.
    
    Args:
        db: Database session
        
    Returns:
        Bot mode: "open" or "restricted"
    """
    bot_mode = db.query(BotMode).first()
    if not bot_mode:
        return "open"
    return bot_mode.mode


def set_bot_mode(db: Session, mode: str, changed_by: int):
    """
    Set bot mode.
    
    Args:
        db: Database session
        mode: "open" or "restricted"
        changed_by: User ID who changed the mode
    """
    bot_mode = db.query(BotMode).first()
    if not bot_mode:
        bot_mode = BotMode(mode=mode, changed_by=changed_by)
        db.add(bot_mode)
    else:
        bot_mode.mode = mode
        bot_mode.changed_by = changed_by
    
    db.commit()

