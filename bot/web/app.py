"""
VersionCheckBot Web Management Panel — FastAPI Application

SPDX-License-Identifier: AGPL-3.0-or-later
Copyright (c) 2024 VersionCheckBot Contributors
"""
import os
import logging
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from bot.web.auth import create_access_token, get_web_password
from bot.web.routers import settings, users, subscriptions, broadcast, scheduler, cache, logs

log = logging.getLogger(__name__)

app = FastAPI(
    title="VersionCheckBot Admin Panel",
    description="Web panel for managing VersionCheckBot",
    version="2.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

# CORS — restrict to localhost in production; relax only if behind a reverse proxy
_allowed_origins = os.getenv(
    "WEB_CORS_ORIGINS",
    "http://localhost:8000,http://127.0.0.1:8000,http://localhost:3000",
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── routers ──────────────────────────────────────────────────────────────────
app.include_router(settings.router)
app.include_router(users.router)
app.include_router(subscriptions.router)
app.include_router(broadcast.router)
app.include_router(scheduler.router)
app.include_router(cache.router)
app.include_router(logs.router)


# ── auth endpoints ────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    password: str


@app.post("/api/auth/login", tags=["auth"])
def login(req: LoginRequest):
    """Exchange password for a JWT Bearer token."""
    if req.password != get_web_password():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect password",
        )
    token = create_access_token()
    return {"access_token": token, "token_type": "bearer", "expires_hours": 24}


# ── health ────────────────────────────────────────────────────────────────────

@app.get("/api/health", tags=["system"])
def health():
    """Public health probe — no auth required."""
    try:
        from bot.database.db import engine
        with engine.connect():
            db_ok = True
    except Exception:
        db_ok = False

    return {
        "status": "ok",
        "database_connected": db_ok,
        "version": "2.0.0",
        "timestamp": datetime.utcnow().isoformat(),
    }


# ── stats (protected) ─────────────────────────────────────────────────────────

@app.get("/api/stats", tags=["system"])
def get_stats():
    """Aggregate dashboard statistics."""
    from bot.database.db import SessionLocal
    from bot.models.user import User
    from bot.models.subscription import Subscription
    from bot.models.query_history import QueryHistory
    from bot.models.cve_record import CVERecord
    from sqlalchemy import func

    db = SessionLocal()
    try:
        total_users = db.query(func.count(User.user_id)).scalar() or 0
        active_users = (
            db.query(func.count(User.user_id))
            .filter(User.is_active == True)  # noqa: E712
            .scalar() or 0
        )
        total_queries = db.query(func.count(QueryHistory.id)).scalar() or 0
        total_subs = db.query(func.count(Subscription.id)).scalar() or 0
        active_subs = (
            db.query(func.count(Subscription.id))
            .filter(Subscription.is_active == True)  # noqa: E712
            .scalar() or 0
        )
        cve_records = db.query(func.count(CVERecord.id)).scalar() or 0

        return {
            "users": {
                "total": total_users,
                "active": active_users,
            },
            "queries": {
                "total": total_queries,
                "avg_per_user": round(total_queries / max(total_users, 1), 1),
            },
            "subscriptions": {
                "total": total_subs,
                "active": active_subs,
            },
            "cache": {
                "cve_records": cve_records,
            },
            "timestamp": datetime.utcnow().isoformat(),
        }
    finally:
        db.close()


# ── static files & SPA ────────────────────────────────────────────────────────

_static = Path(__file__).parent / "static"
if _static.exists():
    app.mount("/static", StaticFiles(directory=str(_static)), name="static")


@app.get("/", include_in_schema=False)
@app.get("/{full_path:path}", include_in_schema=False)
def spa(full_path: str = ""):
    """Serve the SPA for all non-API routes."""
    index = _static / "index.html"
    if index.exists():
        return FileResponse(str(index))
    return JSONResponse({"error": "Frontend not found"}, status_code=404)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "bot.web.app:app",
        host=os.getenv("WEB_PANEL_HOST", "0.0.0.0"),
        port=int(os.getenv("WEB_PANEL_PORT", "8000")),
        reload=False,
    )
