"""
VersionCheckBot Web Panel — Cache Router

SPDX-License-Identifier: AGPL-3.0-or-later
Copyright (c) 2024 VersionCheckBot Contributors
"""
import os
import logging
from pathlib import Path

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from bot.database.db import get_db
from bot.models.cve_record import CVERecord
from bot.web.auth import verify_token

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/cache", tags=["cache"])

CACHE_DIR = Path(os.getenv("CACHE_DIR", "./cache"))


@router.get("/stats")
def cache_stats(
    db: Session = Depends(get_db),
    _: dict = Depends(verify_token),
):
    """Return cache size statistics."""
    eol_files = list(CACHE_DIR.glob("*.json")) if CACHE_DIR.exists() else []
    eol_size_bytes = sum(f.stat().st_size for f in eol_files)
    cve_count = db.query(CVERecord).count()

    return {
        "eol_cache": {
            "files": len(eol_files),
            "size_kb": round(eol_size_bytes / 1024, 1),
            "path": str(CACHE_DIR),
        },
        "cve_db_cache": {
            "records": cve_count,
        },
    }


@router.delete("/eol")
def clear_eol_cache(_: dict = Depends(verify_token)):
    """Delete all EOL JSON cache files from disk."""
    if not CACHE_DIR.exists():
        return {"status": "ok", "deleted": 0}

    deleted = 0
    for f in CACHE_DIR.glob("*.json"):
        try:
            f.unlink()
            deleted += 1
        except Exception as exc:
            log.error("Failed to delete cache file %s: %s", f, exc)

    return {"status": "ok", "deleted": deleted}


@router.delete("/cve")
def clear_cve_cache(
    db: Session = Depends(get_db),
    _: dict = Depends(verify_token),
):
    """Delete all cached CVE records from the database."""
    count = db.query(CVERecord).count()
    db.query(CVERecord).delete()
    db.commit()
    return {"status": "ok", "deleted": count}


@router.delete("/all")
def clear_all_cache(
    db: Session = Depends(get_db),
    _: dict = Depends(verify_token),
):
    """Clear both EOL file cache and CVE database cache."""
    eol_deleted = 0
    if CACHE_DIR.exists():
        for f in CACHE_DIR.glob("*.json"):
            try:
                f.unlink()
                eol_deleted += 1
            except Exception:
                pass

    cve_count = db.query(CVERecord).count()
    db.query(CVERecord).delete()
    db.commit()

    return {"status": "ok", "eol_deleted": eol_deleted, "cve_deleted": cve_count}
