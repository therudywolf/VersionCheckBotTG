"""
VersionCheckBot Web Panel — Scheduler Router

SPDX-License-Identifier: AGPL-3.0-or-later
Copyright (c) 2024 VersionCheckBot Contributors
"""
import os
import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from bot.database.db import get_db
from bot.models.subscription import Subscription
from bot.web.auth import verify_token

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/scheduler", tags=["scheduler"])


@router.get("/status")
def scheduler_status(
    db: Session = Depends(get_db),
    _: dict = Depends(verify_token),
):
    """Return scheduler configuration and last-run statistics."""
    interval = int(os.getenv("SCHEDULER_INTERVAL", "21600"))
    hours, rem = divmod(interval, 3600)
    minutes = rem // 60

    last_checked = db.query(func.max(Subscription.last_checked)).scalar()
    active_subs = (
        db.query(func.count(Subscription.id))
        .filter(Subscription.is_active == True)  # noqa: E712
        .scalar() or 0
    )
    total_subs = db.query(func.count(Subscription.id)).scalar() or 0

    return {
        "interval_seconds": interval,
        "interval_human": f"{hours}h {minutes}m" if hours else f"{minutes}m",
        "last_check": last_checked.isoformat() if last_checked else None,
        "active_subscriptions": active_subs,
        "total_subscriptions": total_subs,
        "note": (
            "Scheduler runs inside the bot process. "
            "Change SCHEDULER_INTERVAL in Settings and restart the bot to apply."
        ),
    }
