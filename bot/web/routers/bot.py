"""
VersionCheckBot Web Panel — Bot Worker Control

SPDX-License-Identifier: AGPL-3.0-or-later
Copyright (c) 2024 VersionCheckBot Contributors
"""
import json
import os
import logging
from pathlib import Path
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException

from bot.web.auth import verify_token

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/bot", tags=["bot"])

DATA_DIR = Path(os.getenv("DATA_DIR", "./data"))
HEARTBEAT_FILE = DATA_DIR / ".bot_heartbeat"
RESTART_FILE = DATA_DIR / ".restart_requested"

# Heartbeat is written every 15 s by the worker — give it 2× headroom
ALIVE_WINDOW = timedelta(seconds=45)


@router.get("/status")
def bot_status(_: dict = Depends(verify_token)):
    """Return the bot worker's real status from its heartbeat file."""
    if not HEARTBEAT_FILE.exists():
        return {
            "status": "unknown",
            "alive": False,
            "message": "No heartbeat file — bot worker has not started yet",
            "heartbeat_file": str(HEARTBEAT_FILE),
        }

    try:
        data = json.loads(HEARTBEAT_FILE.read_text())
    except Exception as exc:
        return {
            "status": "error",
            "alive": False,
            "message": f"Corrupt heartbeat file: {exc}",
        }

    alive = False
    age_seconds = None
    ts = data.get("timestamp")
    if ts:
        try:
            beat_at = datetime.fromisoformat(ts)
            now = datetime.now(timezone.utc)
            age = now - beat_at
            age_seconds = round(age.total_seconds(), 1)
            alive = age < ALIVE_WINDOW
        except Exception:
            pass

    restart_pending = RESTART_FILE.exists()

    return {
        **data,
        "alive": alive,
        "age_seconds": age_seconds,
        "restart_pending": restart_pending,
    }


@router.post("/restart")
def restart_bot(_: dict = Depends(verify_token)):
    """Signal the bot worker to exit so Docker respawns it with fresh .env."""
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        RESTART_FILE.write_text(datetime.now(timezone.utc).isoformat())
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Cannot write restart file: {exc}")

    return {
        "status": "ok",
        "note": "Restart signal sent. Bot will exit within 15 s and Docker will respawn it.",
    }
