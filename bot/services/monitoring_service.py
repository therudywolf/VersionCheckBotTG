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
        self.db = db
        self.version_service = version_service
    
    async def get_or_create_user(self, user_id: int, username: Optional[str] = None) -> User:
        """Get or create a user."""
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
        """Subscribe user to a product/version."""
        if not validate_product_slug(product_slug):
            return False, f"Неверный формат названия продукта: {product_slug}"
        
        # Resolve slug to canonical name before checking
        resolved_slug = await self.version_service.resolve_slug(product_slug)
        
        products = await self.version_service.products()
        if resolved_slug not in products:
            from bot.utils.fuzzy import sugg
            suggestions = sugg(product_slug, products, n=3)
            if suggestions:
                return False, f"Продукт не найден. Возможно, вы имели в виду: {', '.join(suggestions[:3])}"
            return False, f"Продукт '{product_slug}' не найден."
        
        user = await self.get_or_create_user(user_id)
        
        existing = self.db.query(Subscription).filter(
            and_(
                Subscription.user_id == user_id,
                Subscription.product_slug == resolved_slug,
                Subscription.version == version,
                Subscription.is_active == True
            )
        ).first()
        
        if existing:
            return False, f"Вы уже подписаны на {resolved_slug}" + (f" {version}" if version else "")
        
        subscription = Subscription(
            user_id=user_id,
            product_slug=resolved_slug,
            version=version,
            is_active=True
        )
        self.db.add(subscription)
        self.db.commit()
        self.db.refresh(subscription)
        
        log.info(f"User {user_id} subscribed to {resolved_slug} {version or ''}")
        return True, f"Подписка на {resolved_slug}" + (f" {version}" if version else "") + " создана"
    
    async def unsubscribe(self, user_id: int, subscription_id: int) -> Tuple[bool, str]:
        """Unsubscribe user from a subscription."""
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
        """Get all active subscriptions for a user."""
        return self.db.query(Subscription).filter(
            and_(
                Subscription.user_id == user_id,
                Subscription.is_active == True
            )
        ).all()
    
    async def check_subscription(self, subscription: Subscription) -> Optional[Dict]:
        """Check a subscription and return status change if any."""
        try:
            data = await self.version_service.releases(subscription.product_slug)
            if not data:
                return None
            
            rel = self.version_service.find_release(data, subscription.version)
            if rel is None:
                return None

            current_status = self.version_service.release_status(rel)
            
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
            
            subscription.last_checked = datetime.utcnow()
            self.db.commit()
            
            return None
        except Exception as e:
            log.error(f"Error checking subscription {subscription.id}: {e}")
            return None
    
    async def check_all_subscriptions(self, batch_size: int = 10) -> List[Dict]:
        """Check all active subscriptions with batch processing."""
        import asyncio

        active_subscriptions = self.db.query(Subscription).filter(
            Subscription.is_active == True
        ).all()
        
        changes = []
        
        for i in range(0, len(active_subscriptions), batch_size):
            batch = active_subscriptions[i:i + batch_size]
            batch_tasks = [self.check_subscription(sub) for sub in batch]
            batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
            
            for result in batch_results:
                if isinstance(result, dict) and result:
                    changes.append(result)
                elif isinstance(result, Exception):
                    log.error(f"Error checking subscription: {result}")
        
        return changes
