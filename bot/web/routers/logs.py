"""
VersionCheckBot Web Panel — Logs Router

SPDX-License-Identifier: AGPL-3.0-or-later
Copyright (c) 2024 VersionCheckBot Contributors
"""
import os
import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse

from bot.web.auth import verify_token

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/logs", tags=["logs"])

LOG_DIR = Path(os.getenv("LOG_DIR", "./logs"))
LOG_FILE = LOG_DIR / "bot.log"
ERRORS_FILE = LOG_DIR / "errors.log"


@router.get("")
def get_logs(
    lines: int = Query(200, ge=10, le=2000),
    level: Optional[str] = None,
    file: str = Query("bot", pattern="^(bot|errors)$"),
    _: dict = Depends(verify_token),
):
    """Return the last N lines from the log file, optionally filtered by level."""
    target = LOG_FILE if file == "bot" else ERRORS_FILE

    if not target.exists():
        return {"lines": [], "total_lines": 0, "file": str(target), "exists": False}

    try:
        with open(target, "r", encoding="utf-8", errors="replace") as fh:
            all_lines = fh.readlines()

        recent = all_lines[-lines:]

        if level:
            lvl = level.upper()
            recent = [ln for ln in recent if lvl in ln]

        return {
            "lines": [ln.rstrip() for ln in recent],
            "total_lines": len(all_lines),
            "file": str(target),
            "exists": True,
        }
    except Exception as exc:
        return {"lines": [], "error": str(exc), "exists": True}


@router.get("/download")
def download_logs(
    file: str = Query("bot", pattern="^(bot|errors)$"),
    _: dict = Depends(verify_token),
):
    """Download a log file."""
    target = LOG_FILE if file == "bot" else ERRORS_FILE
    if not target.exists():
        raise HTTPException(status_code=404, detail="Log file not found")
    return FileResponse(str(target), filename=target.name, media_type="text/plain")
