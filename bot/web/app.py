"""
VersionCheckBot Web Management Panel - FastAPI Application

SPDX-License-Identifier: AGPL-3.0-or-later
Copyright (c) 2024 VersionCheckBot Contributors
"""

import logging
from typing import Optional
from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from pathlib import Path

# Set up logging
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="VersionCheckBot Management Panel",
    description="Web panel for managing VersionCheckBot",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:*", "127.0.0.1:*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ────────────────────────────────────────────────
# Models
# ────────────────────────────────────────────────

class BotStatus(BaseModel):
    """Bot status information"""
    running: bool
    uptime_seconds: float
    database_connected: bool
    version: str
    timestamp: datetime


class UserStats(BaseModel):
    """User statistics"""
    total_users: int
    active_users_24h: int
    total_queries: int
    average_queries_per_user: float


class SubscriptionStats(BaseModel):
    """Subscription statistics"""
    total_subscriptions: int
    active_subscriptions: int
    expiring_soon: int


class SystemStats(BaseModel):
    """Complete system statistics"""
    bot_status: BotStatus
    user_stats: UserStats
    subscription_stats: SubscriptionStats
    cache_status: dict


# ────────────────────────────────────────────────
# API Routes
# ────────────────────────────────────────────────

@app.get("/api/health", response_model=BotStatus)
async def health_check():
    """Check bot health status"""
    from config import settings
    from bot.database.db import init_db

    try:
        db_connected = await init_db()
    except Exception as e:
        logger.error(f"Database connection error: {e}")
        db_connected = False

    return BotStatus(
        running=True,
        uptime_seconds=0,
        database_connected=db_connected,
        version="1.0.0",
        timestamp=datetime.now()
    )


@app.get("/api/stats", response_model=SystemStats)
async def get_system_stats():
    """Get complete system statistics"""
    from bot.database.db import get_session
    from bot.models.user import User
    from bot.models.subscription import Subscription
    from bot.models.query_history import QueryHistory
    from sqlalchemy import func, select

    async with get_session() as session:
        # User stats
        total_users = await session.scalar(select(func.count(User.id)))
        total_queries = await session.scalar(select(func.count(QueryHistory.id)))

        active_24h = await session.scalar(
            select(func.count(User.id)).where(
                User.last_seen >= datetime.now() - timedelta(hours=24)
            )
        )

        avg_queries = total_queries / max(total_users, 1)

        # Subscription stats
        total_subs = await session.scalar(select(func.count(Subscription.id)))
        active_subs = await session.scalar(
            select(func.count(Subscription.id)).where(Subscription.active == True)
        )

        expiring_subs = await session.scalar(
            select(func.count(Subscription.id)).where(
                Subscription.expiry_date <= datetime.now() + timedelta(days=7),
                Subscription.expiry_date > datetime.now()
            )
        )

        # Bot status
        try:
            db_connected = True
        except:
            db_connected = False

        bot_status = BotStatus(
            running=True,
            uptime_seconds=0,
            database_connected=db_connected,
            version="1.0.0",
            timestamp=datetime.now()
        )

        user_stats = UserStats(
            total_users=total_users or 0,
            active_users_24h=active_24h or 0,
            total_queries=total_queries or 0,
            average_queries_per_user=avg_queries or 0.0
        )

        subscription_stats = SubscriptionStats(
            total_subscriptions=total_subs or 0,
            active_subscriptions=active_subs or 0,
            expiring_soon=expiring_subs or 0
        )

        return SystemStats(
            bot_status=bot_status,
            user_stats=user_stats,
            subscription_stats=subscription_stats,
            cache_status={"cached_products": 0, "cached_cves": 0}
        )


@app.get("/api/users")
async def list_users(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0)
):
    """List users with pagination"""
    from bot.database.db import get_session
    from bot.models.user import User
    from sqlalchemy import select

    async with get_session() as session:
        users = await session.execute(
            select(User).limit(limit).offset(offset)
        )
        return {
            "users": [
                {
                    "id": u.id,
                    "username": u.username,
                    "first_name": u.first_name,
                    "joined_at": u.joined_at,
                    "last_seen": u.last_seen
                }
                for u in users.scalars()
            ]
        }


@app.get("/api/subscriptions")
async def list_subscriptions(
    user_id: Optional[int] = None,
    product: Optional[str] = None,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0)
):
    """List subscriptions with filters"""
    from bot.database.db import get_session
    from bot.models.subscription import Subscription
    from sqlalchemy import select

    async with get_session() as session:
        query = select(Subscription)

        if user_id:
            query = query.where(Subscription.user_id == user_id)
        if product:
            query = query.where(Subscription.product.ilike(f"%{product}%"))

        subs = await session.execute(query.limit(limit).offset(offset))

        return {
            "subscriptions": [
                {
                    "id": s.id,
                    "user_id": s.user_id,
                    "product": s.product,
                    "version": s.version,
                    "created_at": s.created_at,
                    "active": s.active
                }
                for s in subs.scalars()
            ]
        }


@app.post("/api/admin/broadcast")
async def broadcast_message(
    message: str,
    user_ids: Optional[list[int]] = None
):
    """Send broadcast message to users"""
    from bot.services.notification_service import NotificationService

    if not message or len(message) == 0:
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    # In production, add proper authentication
    logger.info(f"Broadcasting message to {len(user_ids or [])} users")

    return {
        "status": "broadcast_queued",
        "message_preview": message[:100],
        "recipients_count": len(user_ids or [])
    }


@app.get("/")
async def root():
    """Serve main page"""
    return FileResponse(Path(__file__).parent / "static" / "index.html")


# Mount static files
static_path = Path(__file__).parent / "static"
if static_path.exists():
    app.mount("/static", StaticFiles(directory=str(static_path)), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
