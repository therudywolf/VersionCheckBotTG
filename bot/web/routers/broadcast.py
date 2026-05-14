"""
VersionCheckBot Web Panel — Broadcast Router

SPDX-License-Identifier: AGPL-3.0-or-later
Copyright (c) 2024 VersionCheckBot Contributors
"""
import os
import logging
from typing import List, Optional

import aiohttp
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import desc

from bot.database.db import get_db
from bot.models.user import User
from bot.models.notification import Notification
from bot.web.auth import verify_token

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin", tags=["broadcast"])


class BroadcastRequest(BaseModel):
    message: str
    target: str = "all"          # "all" | "active" | "ids"
    user_ids: Optional[List[int]] = None
    parse_mode: str = "Markdown"


@router.get("/broadcasts")
def list_broadcasts(
    limit: int = 20,
    db: Session = Depends(get_db),
    _: dict = Depends(verify_token),
):
    """List recently sent broadcast notifications."""
    rows = (
        db.query(Notification)
        .filter(Notification.notification_type == "broadcast")
        .order_by(desc(Notification.sent_at))
        .limit(limit)
        .all()
    )
    return {
        "broadcasts": [
            {
                "id": b.id,
                "user_id": b.user_id,
                "preview": b.message[:120] + ("…" if len(b.message) > 120 else ""),
                "sent_at": b.sent_at.isoformat() if b.sent_at else None,
            }
            for b in rows
        ]
    }


@router.post("/broadcast")
async def send_broadcast(
    req: BroadcastRequest,
    db: Session = Depends(get_db),
    _: dict = Depends(verify_token),
):
    """Send a Telegram message to selected users via the Bot API."""
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    token = os.getenv("BOT_TOKEN", "")
    if not token:
        raise HTTPException(status_code=500, detail="BOT_TOKEN not configured")

    # Resolve recipient list
    if req.target == "ids" and req.user_ids:
        user_ids = req.user_ids
    elif req.target == "active":
        user_ids = [u.user_id for u in db.query(User).filter(User.is_active == True).all()]  # noqa: E712
    else:
        user_ids = [u.user_id for u in db.query(User).all()]

    if not user_ids:
        return {"status": "no_recipients", "sent": 0, "failed": 0, "total": 0}

    sent = failed = 0
    url = f"https://api.telegram.org/bot{token}/sendMessage"

    async with aiohttp.ClientSession() as session:
        for uid in user_ids:
            try:
                async with session.post(
                    url,
                    json={"chat_id": uid, "text": req.message, "parse_mode": req.parse_mode},
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    data = await resp.json()
                    if data.get("ok"):
                        sent += 1
                        db.add(Notification(
                            user_id=uid,
                            subscription_id=None,
                            message=req.message,
                            notification_type="broadcast",
                        ))
                    else:
                        failed += 1
                        log.warning("Broadcast to %d failed: %s", uid, data.get("description"))
            except Exception as exc:
                failed += 1
                log.error("Error broadcasting to %d: %s", uid, exc)

    db.commit()
    return {"status": "done", "sent": sent, "failed": failed, "total": len(user_ids)}
