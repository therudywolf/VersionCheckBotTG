"""Service for managing subscriptions and monitoring products."""
import logging
from datetime import datetime
from typing import List, Optional, Dict, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_

from bot.models import User, Subscription
from bot.services.version_service import VersionService
from bot.utils.parser import parse, validate_product_slug

log = logging.getLogger(__name__)


class MonitoringService:
    """Service for managing product subscriptions and monitoring."""
    
    def __init__(self, db: Session, version_service: VersionService):
        """
        Initialize monitoring service.
        
        Args:
            db: Database session
            version_service: Version service instance
        """
        self.db = db
        self.version_service = version_service
    
    async def get_or_create_user(self, user_id: int, username: Optional[str] = None) -> User:
        """
        Get or create a user.
        
        Args:
            user_id: Telegram user ID
            username: Optional username
            
        Returns:
            User instance
        """
        user = self.db.query(User).filter(User.user_id == user_id).first()
        if not user:
            user = User(user_id=user_id, username=username)
            self.db.add(user)
            self.db.commit()
            self.db.refresh(user)
            log.info(f"Created new user: {user_id}")
        elif username and user.username != username:
            user.username = username
            self.db.commit()
        return user
    
    async def subscribe(
        self,
        user_id: int,
        product_slug: str,
        version: Optional[str] = None
    ) -> Tuple[bool, str]:
        """
        Subscribe user to a product/version.
        
        Args:
            user_id: Telegram user ID
            product_slug: Product slug
            version: Optional version string
            
        Returns:
            Tuple of (success, message)
        """
        # Validate product slug
        if not validate_product_slug(product_slug):
            return False, f"Неверный формат названия продукта: {product_slug}"
        
        # Check if product exists
        products = await self.version_service.products()
        if product_slug not in products:
            # Try fuzzy match
            from bot.utils.fuzzy import sugg
            suggestions = sugg(product_slug, products, n=3)
            if suggestions:
                return False, f"Продукт не найден. Возможно, вы имели в виду: {', '.join(suggestions[:3])}"
            return False, f"Продукт '{product_slug}' не найден."
        
        # Get or create user
        user = await self.get_or_create_user(user_id)
        
        # Check if subscription already exists
        existing = self.db.query(Subscription).filter(
            and_(
                Subscription.user_id == user_id,
                Subscription.product_slug == product_slug,
                Subscription.version == version,
                Subscription.is_active == True
            )
        ).first()
        
        if existing:
            return False, f"Вы уже подписаны на {product_slug}" + (f" {version}" if version else "")
        
        # Create subscription
        subscription = Subscription(
            user_id=user_id,
            product_slug=product_slug,
            version=version,
            is_active=True
        )
        self.db.add(subscription)
        self.db.commit()
        self.db.refresh(subscription)
        
        log.info(f"User {user_id} subscribed to {product_slug} {version or ''}")
        return True, f"Подписка на {product_slug}" + (f" {version}" if version else "") + " создана"
    
    async def unsubscribe(self, user_id: int, subscription_id: int) -> Tuple[bool, str]:
        """
        Unsubscribe user from a subscription.
        
        Args:
            user_id: Telegram user ID
            subscription_id: Subscription ID
            
        Returns:
            Tuple of (success, message)
        """
        subscription = self.db.query(Subscription).filter(
            and_(
                Subscription.id == subscription_id,
                Subscription.user_id == user_id
            )
        ).first()
        
        if not subscription:
            return False, "Подписка не найдена"
        
        subscription.is_active = False
        self.db.commit()
        
        log.info(f"User {user_id} unsubscribed from {subscription.product_slug}")
        return True, f"Подписка на {subscription.product_slug} отменена"
    
    async def get_user_subscriptions(self, user_id: int) -> List[Subscription]:
        """
        Get all active subscriptions for a user.
        
        Args:
            user_id: Telegram user ID
            
        Returns:
            List of active subscriptions
        """
        return self.db.query(Subscription).filter(
            and_(
                Subscription.user_id == user_id,
                Subscription.is_active == True
            )
        ).all()
    
    async def check_subscription(self, subscription: Subscription) -> Optional[Dict]:
        """
        Check a subscription and return status change if any.
        
        Args:
            subscription: Subscription instance
            
        Returns:
            Dictionary with status change info or None
        """
        try:
            data = await self.version_service.releases(subscription.product_slug)
            if not data:
                return None
            
            # Find the relevant release
            rel = None
            if subscription.version:
                v = subscription.version.lower()
                for r in data:
                    if v in {str(r.get('cycle', '')).lower(), str(r.get('latest', '')).lower()}:
                        rel = r
                        break
            
            if rel is None:
                rel = data[0]
            
            # Determine current status
            is_supported = str(rel.get('support') or rel.get('supported')).lower() in {
                "true", "yes", "active", "supported"
            }
            eol = rel.get('eol')
            current_status = "supported" if is_supported else ("eol" if eol else "unknown")
            
            # Check if status changed
            if subscription.last_status != current_status:
                old_status = subscription.last_status or "unknown"
                subscription.last_status = current_status
                subscription.last_checked = datetime.utcnow()
                self.db.commit()
                
                return {
                    "subscription": subscription,
                    "old_status": old_status,
                    "new_status": current_status,
                    "release": rel
                }
            
            # Update last checked time
            subscription.last_checked = datetime.utcnow()
            self.db.commit()
            
            return None
        except Exception as e:
            log.error(f"Error checking subscription {subscription.id}: {e}")
            return None
    
    async def check_all_subscriptions(self) -> List[Dict]:
        """
        Check all active subscriptions.
        
        Returns:
            List of status change dictionaries
        """
        active_subscriptions = self.db.query(Subscription).filter(
            Subscription.is_active == True
        ).all()
        
        changes = []
        for subscription in active_subscriptions:
            change = await self.check_subscription(subscription)
            if change:
                changes.append(change)
        
        return changes

