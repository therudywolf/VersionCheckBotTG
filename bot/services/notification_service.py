"""Service for sending notifications to users."""
import logging
from typing import Optional
from datetime import datetime
from sqlalchemy.orm import Session
from telegram import Bot

from bot.models import Notification
from config import settings

log = logging.getLogger(__name__)


class NotificationService:
    """Service for sending notifications to Telegram users."""
    
    def __init__(self, db: Session, bot: Bot):
        """
        Initialize notification service.
        
        Args:
            db: Database session
            bot: Telegram bot instance
        """
        self.db = db
        self.bot = bot
    
    async def send_notification(
        self,
        user_id: int,
        message: str,
        notification_type: str = "status_change",
        subscription_id: Optional[int] = None
    ) -> bool:
        """
        Send a notification to a user.
        
        Args:
            user_id: Telegram user ID
            message: Notification message
            notification_type: Type of notification
            subscription_id: Optional subscription ID
            
        Returns:
            True if sent successfully, False otherwise
        """
        if not settings.NOTIFICATION_ENABLED:
            log.debug("Notifications are disabled")
            return False
        
        try:
            await self.bot.send_message(chat_id=user_id, text=message)
            
            # Record notification
            notification = Notification(
                user_id=user_id,
                subscription_id=subscription_id,
                message=message,
                notification_type=notification_type
            )
            self.db.add(notification)
            self.db.commit()
            
            log.info(f"Sent notification to user {user_id}: {notification_type}")
            return True
        except Exception as e:
            log.error(f"Failed to send notification to user {user_id}: {e}")
            return False
    
    async def notify_status_change(
        self,
        user_id: int,
        product_slug: str,
        version: Optional[str],
        old_status: str,
        new_status: str,
        subscription_id: Optional[int] = None
    ) -> bool:
        """
        Send a status change notification.
        
        Args:
            user_id: Telegram user ID
            product_slug: Product slug
            version: Optional version
            old_status: Old status
            new_status: New status
            subscription_id: Optional subscription ID
            
        Returns:
            True if sent successfully, False otherwise
        """
        status_emoji = "✅" if new_status == "supported" else "❌"
        version_str = f" {version}" if version else ""
        message = (
            f"{status_emoji} *Изменение статуса*\n\n"
            f"Продукт: *{product_slug}*{version_str}\n"
            f"Статус: {old_status} → {new_status}"
        )
        
        return await self.send_notification(
            user_id=user_id,
            message=message,
            notification_type="status_change",
            subscription_id=subscription_id
        )
    
    async def notify_new_cve(
        self,
        user_id: int,
        product_slug: str,
        version: Optional[str],
        cve_id: str,
        severity: Optional[str],
        subscription_id: Optional[int] = None
    ) -> bool:
        """
        Send a new CVE notification.
        
        Args:
            user_id: Telegram user ID
            product_slug: Product slug
            version: Optional version
            cve_id: CVE ID
            severity: CVE severity
            subscription_id: Optional subscription ID
            
        Returns:
            True if sent successfully, False otherwise
        """
        severity_emoji = {
            "CRITICAL": "🔴",
            "HIGH": "🟠",
            "MEDIUM": "🟡",
            "LOW": "🟢"
        }.get(severity, "⚪")
        
        version_str = f" {version}" if version else ""
        message = (
            f"{severity_emoji} *Новый CVE*\n\n"
            f"Продукт: *{product_slug}*{version_str}\n"
            f"CVE: *{cve_id}*\n"
            f"Критичность: {severity or 'не указана'}"
        )
        
        return await self.send_notification(
            user_id=user_id,
            message=message,
            notification_type="new_cve",
            subscription_id=subscription_id
        )

