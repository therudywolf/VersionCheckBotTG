"""
VersionCheckBot - Telegram bot for monitoring software versions and CVE vulnerabilities

SPDX-License-Identifier: AGPL-3.0-or-later
Copyright (c) 2024 VersionCheckBot Contributors
"""
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
        self.bot = bot
        self.running = False
        self._task = None
        self.version_service = None
        self._shutdown_event = asyncio.Event()
    
    async def check_subscriptions_task(self):
        """Periodically check all subscriptions for status changes."""
        log.info("Starting subscription check task")
        
        if not self.version_service:
            self.version_service = VersionService()
        
        while self.running:
            try:
                if self._shutdown_event.is_set():
                    break
                
                db_gen = get_db()
                db = next(db_gen)
                try:
                    monitoring_service = MonitoringService(db, self.version_service)
                    notification_service = NotificationService(db, self.bot)
                    
                    changes = await monitoring_service.check_all_subscriptions(batch_size=10)
                    
                    for change in changes:
                        subscription = change["subscription"]
                        await notification_service.notify_status_change(
                            user_id=subscription.user_id,
                            product_slug=subscription.product_slug,
                            version=subscription.version,
                            old_status=change["old_status"],
                            new_status=change["new_status"],
                            subscription_id=subscription.id
                        )
                    
                    if changes:
                        log.info(f"Sent {len(changes)} status change notifications")
                finally:
                    db.close()
                
                try:
                    await asyncio.wait_for(
                        self._shutdown_event.wait(),
                        timeout=settings.SCHEDULER_INTERVAL
                    )
                    break
                except asyncio.TimeoutError:
                    pass
            except Exception as e:
                log.error(f"Error in subscription check task: {e}", exc_info=True)
                try:
                    await asyncio.wait_for(self._shutdown_event.wait(), timeout=60)
                    break
                except asyncio.TimeoutError:
                    pass
    
    async def check_cve_task(self):
        """Periodically check for new CVEs for subscribed products."""
        log.info("Starting CVE check task")
        
        if not self.version_service:
            self.version_service = VersionService()
        
        while self.running:
            try:
                if self._shutdown_event.is_set():
                    break
                
                db_gen = get_db()
                db = next(db_gen)
                try:
                    cve_service = CVEService(db)
                    notification_service = NotificationService(db, self.bot)
                    
                    from bot.models import Subscription, Notification
                    subscriptions = db.query(Subscription).filter(
                        Subscription.is_active == True
                    ).all()
                    
                    products = {}
                    for sub in subscriptions:
                        key = (sub.product_slug, sub.version)
                        if key not in products:
                            products[key] = []
                        products[key].append(sub)
                    
                    for (product_slug, version), subs in products.items():
                        try:
                            recent_cves = await cve_service.get_recent_cves(product_slug, days=7)
                            
                            for cve in recent_cves:
                                cve_id = cve.get("cve_id", "")
                                if not cve_id:
                                    continue

                                for sub in subs:
                                    already_notified = db.query(Notification).filter(
                                        Notification.user_id == sub.user_id,
                                        Notification.notification_type == "new_cve",
                                        Notification.message.like(f"%{cve_id}%")
                                    ).first()
                                    
                                    if not already_notified:
                                        await notification_service.notify_new_cve(
                                            user_id=sub.user_id,
                                            product_slug=product_slug,
                                            version=version,
                                            cve_id=cve_id,
                                            severity=cve.get("severity"),
                                            subscription_id=sub.id
                                        )
                        except Exception as e:
                            log.error(f"Error checking CVEs for {product_slug}: {e}")
                finally:
                    db.close()
                
                try:
                    await asyncio.wait_for(
                        self._shutdown_event.wait(),
                        timeout=86400
                    )
                    break
                except asyncio.TimeoutError:
                    pass
            except Exception as e:
                log.error(f"Error in CVE check task: {e}", exc_info=True)
                try:
                    await asyncio.wait_for(self._shutdown_event.wait(), timeout=3600)
                    break
                except asyncio.TimeoutError:
                    pass
    
    async def start(self):
        """Start the scheduler."""
        if self.running:
            log.warning("Scheduler is already running")
            return
        
        self.running = True
        log.info("Starting scheduler")
        self._task = asyncio.create_task(self._run_tasks())
    
    async def stop(self):
        """Stop the scheduler gracefully."""
        if not self.running:
            return
        
        log.info("Stopping scheduler gracefully...")
        self.running = False
        self._shutdown_event.set()
        
        if self.version_service:
            await self.version_service.close()
        
        if self._task:
            try:
                await asyncio.wait_for(self._task, timeout=30)
            except asyncio.TimeoutError:
                log.warning("Scheduler tasks did not stop in time, cancelling...")
                self._task.cancel()
                try:
                    await self._task
                except asyncio.CancelledError:
                    pass
        
        log.info("Scheduler stopped")
    
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
