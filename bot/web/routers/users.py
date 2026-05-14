"""
VersionCheckBot Web Panel — Users Router

SPDX-License-Identifier: AGPL-3.0-or-later
Copyright (c) 2024 VersionCheckBot Contributors
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from bot.database.db import get_db
from bot.models.user import User
from bot.models.query_history import QueryHistory
from bot.models.admin import Access
from bot.web.auth import verify_token

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("")
def list_users(
    search: Optional[str] = None,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    _: dict = Depends(verify_token),
):
    """List users with optional username search and pagination."""
    query = db.query(User)
    if search:
        query = query.filter(User.username.ilike(f"%{search}%"))

    total = query.count()
    users = query.order_by(desc(User.created_at)).limit(limit).offset(offset).all()

    result = []
    for u in users:
        qcount = (
            db.query(func.count(QueryHistory.id))
            .filter(QueryHistory.user_id == u.user_id)
            .scalar() or 0
        )
        access = db.query(Access).filter(Access.user_id == u.user_id).first()
        result.append({
            "user_id": u.user_id,
            "username": u.username,
            "language": u.language,
            "is_active": u.is_active,
            "is_admin": access.is_admin if access else False,
            "has_access": access.has_access if access else True,
            "query_count": qcount,
            "created_at": u.created_at.isoformat() if u.created_at else None,
            "updated_at": u.updated_at.isoformat() if u.updated_at else None,
        })

    return {"users": result, "total": total, "limit": limit, "offset": offset}


@router.get("/{user_id}/history")
def get_user_history(
    user_id: int,
    limit: int = Query(30, ge=1, le=100),
    db: Session = Depends(get_db),
    _: dict = Depends(verify_token),
):
    """Get recent query history for a specific user."""
    rows = (
        db.query(QueryHistory)
        .filter(QueryHistory.user_id == user_id)
        .order_by(desc(QueryHistory.created_at))
        .limit(limit)
        .all()
    )
    return {
        "user_id": user_id,
        "history": [
            {
                "id": h.id,
                "query_text": h.query_text,
                "query_type": h.query_type,
                "result_summary": h.result_summary,
                "created_at": h.created_at.isoformat() if h.created_at else None,
            }
            for h in rows
        ],
    }


@router.post("/{user_id}/ban")
def ban_user(
    user_id: int,
    db: Session = Depends(get_db),
    _: dict = Depends(verify_token),
):
    """Deactivate a user (ban from bot)."""
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_active = False
    db.commit()
    return {"status": "ok", "user_id": user_id, "is_active": False}


@router.post("/{user_id}/unban")
def unban_user(
    user_id: int,
    db: Session = Depends(get_db),
    _: dict = Depends(verify_token),
):
    """Reactivate a user."""
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_active = True
    db.commit()
    return {"status": "ok", "user_id": user_id, "is_active": True}


@router.post("/{user_id}/admin")
def make_admin(
    user_id: int,
    db: Session = Depends(get_db),
    _: dict = Depends(verify_token),
):
    """Grant admin rights to a user."""
    access = db.query(Access).filter(Access.user_id == user_id).first()
    if access:
        access.is_admin = True
        access.has_access = True
    else:
        access = Access(user_id=user_id, is_admin=True, has_access=True)
        db.add(access)
    db.commit()
    return {"status": "ok", "user_id": user_id, "is_admin": True}


@router.delete("/{user_id}/admin")
def remove_admin(
    user_id: int,
    db: Session = Depends(get_db),
    _: dict = Depends(verify_token),
):
    """Revoke admin rights from a user."""
    access = db.query(Access).filter(Access.user_id == user_id).first()
    if access:
        access.is_admin = False
        db.commit()
    return {"status": "ok", "user_id": user_id, "is_admin": False}
