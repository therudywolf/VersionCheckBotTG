"""
VersionCheckBot Web Panel — Subscriptions Router

SPDX-License-Identifier: AGPL-3.0-or-later
Copyright (c) 2024 VersionCheckBot Contributors
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc

from bot.database.db import get_db
from bot.models.subscription import Subscription
from bot.web.auth import verify_token

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/subscriptions", tags=["subscriptions"])


@router.get("")
def list_subscriptions(
    user_id: Optional[int] = None,
    product: Optional[str] = None,
    active_only: bool = False,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    _: dict = Depends(verify_token),
):
    """List subscriptions with optional filters."""
    query = db.query(Subscription)
    if user_id:
        query = query.filter(Subscription.user_id == user_id)
    if product:
        query = query.filter(Subscription.product_slug.ilike(f"%{product}%"))
    if active_only:
        query = query.filter(Subscription.is_active == True)  # noqa: E712

    total = query.count()
    subs = query.order_by(desc(Subscription.created_at)).limit(limit).offset(offset).all()

    return {
        "subscriptions": [
            {
                "id": s.id,
                "user_id": s.user_id,
                "product_slug": s.product_slug,
                "version": s.version,
                "last_status": s.last_status,
                "is_active": s.is_active,
                "last_checked": s.last_checked.isoformat() if s.last_checked else None,
                "created_at": s.created_at.isoformat() if s.created_at else None,
            }
            for s in subs
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.patch("/{sub_id}/deactivate")
def deactivate_subscription(
    sub_id: int,
    db: Session = Depends(get_db),
    _: dict = Depends(verify_token),
):
    """Deactivate a subscription (stop monitoring)."""
    sub = db.query(Subscription).filter(Subscription.id == sub_id).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Subscription not found")
    sub.is_active = False
    db.commit()
    return {"status": "ok", "id": sub_id, "is_active": False}


@router.patch("/{sub_id}/activate")
def activate_subscription(
    sub_id: int,
    db: Session = Depends(get_db),
    _: dict = Depends(verify_token),
):
    """Re-activate a subscription."""
    sub = db.query(Subscription).filter(Subscription.id == sub_id).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Subscription not found")
    sub.is_active = True
    db.commit()
    return {"status": "ok", "id": sub_id, "is_active": True}


@router.delete("/{sub_id}")
def delete_subscription(
    sub_id: int,
    db: Session = Depends(get_db),
    _: dict = Depends(verify_token),
):
    """Permanently delete a subscription."""
    sub = db.query(Subscription).filter(Subscription.id == sub_id).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Subscription not found")
    db.delete(sub)
    db.commit()
    return {"status": "deleted", "id": sub_id}
