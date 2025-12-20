"""Background tasks scheduler."""
import asyncio
import logging
from datetime import datetime

from bot.services.monitoring_service import MonitoringService
from bot.services.notification_service import NotificationService
from bot.services.version_service import VersionService
from bot.services.cve_service import CVEService
from bot.database.db import get_db
from config import settings

log = logging.getLogger(__name__)


class Scheduler:
    """Scheduler for background tasks."""
    
    def __init__(self, bot):
        """
        Initialize scheduler.
        
        Args:
            bot: Telegram bot instance
        """
        self.bot = bot
        self.running = False
        self._task = None
    
    async def check_subscriptions_task(self):
        """Periodically check all subscriptions for status changes."""
        log.info("Starting subscription check task")
        
        while self.running:
            try:
                db_gen = get_db()
                db = next(db_gen)
                try:
                    version_service = VersionService()
                    monitoring_service = MonitoringService(db, version_service)
                    notification_service = NotificationService(db, self.bot)
                
                # Check all subscriptions
                changes = await monitoring_service.check_all_subscriptions()
                
                # Send notifications for changes
                for change in changes:
                    subscription = change["subscription"]
                    user_id = subscription.user_id
                    product_slug = subscription.product_slug
                    version = subscription.version
                    old_status = change["old_status"]
                    new_status = change["new_status"]
                    
                    await notification_service.notify_status_change(
                        user_id=user_id,
                        product_slug=product_slug,
                        version=version,
                        old_status=old_status,
                        new_status=new_status,
                        subscription_id=subscription.id
                    )
                
                    if changes:
                        log.info(f"Sent {len(changes)} status change notifications")
                finally:
                    db.close()
                
                # Wait for next interval
                await asyncio.sleep(settings.SCHEDULER_INTERVAL)
            except Exception as e:
                log.error(f"Error in subscription check task: {e}", exc_info=True)
                await asyncio.sleep(60)  # Wait 1 minute before retry
    
    async def check_cve_task(self):
        """Periodically check for new CVEs for subscribed products."""
        log.info("Starting CVE check task")
        
        while self.running:
            try:
                db_gen = get_db()
                db = next(db_gen)
                try:
                    version_service = VersionService()
                    monitoring_service = MonitoringService(db, version_service)
                    cve_service = CVEService(db)
                    notification_service = NotificationService(db, self.bot)
                    
                    # Get all active subscriptions
                    from bot.models import Subscription
                    subscriptions = db.query(Subscription).filter(
                        Subscription.is_active == True
                    ).all()
                
                # Group by product
                products = {}
                for sub in subscriptions:
                    key = (sub.product_slug, sub.version)
                    if key not in products:
                        products[key] = []
                    products[key].append(sub)
                
                # Check for new CVEs
                for (product_slug, version), subs in products.items():
                    try:
                        # Get recent CVEs (last 7 days)
                        recent_cves = await cve_service.get_recent_cves(product_slug, days=7)
                        
                        # Check if any are new (not in database or recently published)
                        for cve in recent_cves:
                            # Check if we already notified about this CVE
                            from bot.models import Notification
                            existing = db.query(Notification).filter(
                                Notification.user_id.in_([s.user_id for s in subs]),
                                Notification.notification_type == "new_cve",
                                Notification.message.like(f"%{cve['cve_id']}%")
                            ).first()
                            
                            if not existing:
                                # Send notifications to all subscribers
                                for sub in subs:
                                    await notification_service.notify_new_cve(
                                        user_id=sub.user_id,
                                        product_slug=product_slug,
                                        version=version,
                                        cve_id=cve.get("cve_id", ""),
                                        severity=cve.get("severity"),
                                        subscription_id=sub.id
                                    )
                    except Exception as e:
                        log.error(f"Error checking CVEs for {product_slug}: {e}")
                finally:
                    db.close()
                
                # Wait 24 hours before next check
                await asyncio.sleep(86400)
            except Exception as e:
                log.error(f"Error in CVE check task: {e}", exc_info=True)
                await asyncio.sleep(3600)  # Wait 1 hour before retry
    
    async def start(self):
        """Start the scheduler."""
        if self.running:
            log.warning("Scheduler is already running")
            return
        
        self.running = True
        log.info("Starting scheduler")
        
        # Start tasks
        self._task = asyncio.create_task(self._run_tasks())
    
    async def stop(self):
        """Stop the scheduler."""
        if not self.running:
            return
        
        self.running = False
        log.info("Stopping scheduler")
        
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
    
    async def _run_tasks(self):
        """Run all scheduled tasks."""
        try:
            await asyncio.gather(
                self.check_subscriptions_task(),
                self.check_cve_task(),
                return_exceptions=True
            )
        except Exception as e:
            log.error(f"Error in scheduler tasks: {e}", exc_info=True)

