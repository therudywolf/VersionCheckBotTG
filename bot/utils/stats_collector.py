"""Statistics collector for user activity."""
import logging
from datetime import datetime
from sqlalchemy.orm import Session

from bot.models.user_stats import UserStats

log = logging.getLogger(__name__)


def record_command(db: Session, user_id: int, command_name: str):
    """
    Record command usage in statistics.
    
    Args:
        db: Database session
        user_id: Telegram user ID
        command_name: Command name (e.g., "check", "subscribe", "cve")
    """
    try:
        stats = db.query(UserStats).filter(UserStats.user_id == user_id).first()
        
        if not stats:
            stats = UserStats(user_id=user_id)
            db.add(stats)
        
        stats.commands_count += 1
        stats.last_command = command_name
        stats.last_activity = datetime.utcnow()
        
        # Increment specific command counter
        if command_name == "check":
            stats.check_commands += 1
        elif command_name == "subscribe":
            stats.subscribe_commands += 1
        elif command_name == "cve":
            stats.cve_commands += 1
        
        db.commit()
    except Exception as e:
        log.error(f"Error recording stats: {e}")
        db.rollback()

