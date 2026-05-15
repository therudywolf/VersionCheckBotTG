"""
VersionCheckBot Web Panel — Settings Router

SPDX-License-Identifier: AGPL-3.0-or-later
Copyright (c) 2024 VersionCheckBot Contributors
"""
import os
import logging
from pathlib import Path
from typing import Optional

import aiohttp
from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from bot.web.auth import verify_token

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/settings", tags=["settings"])

ENV_FILE = Path(os.getenv("ENV_FILE", ".env"))


# ── helpers ──────────────────────────────────────────────────────────────────

def _read_env() -> dict:
    env: dict = {}
    if ENV_FILE.exists():
        for raw in ENV_FILE.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                env[key.strip()] = val.strip()
    return env


def _write_env(updates: dict) -> None:
    """Merge updates into existing .env, preserving comments and order."""
    lines: list[str] = []
    written: set[str] = set()

    if ENV_FILE.exists():
        for raw in ENV_FILE.read_text(encoding="utf-8").splitlines():
            stripped = raw.strip()
            if stripped and not stripped.startswith("#") and "=" in stripped:
                key = stripped.partition("=")[0].strip()
                if key in updates:
                    lines.append(f"{key}={updates[key]}")
                    written.add(key)
                else:
                    lines.append(raw)
            else:
                lines.append(raw)

    for key, val in updates.items():
        if key not in written:
            lines.append(f"{key}={val}")

    ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _mask(value: str, show: int = 4) -> str:
    if not value:
        return ""
    if len(value) <= show * 2:
        return "***"
    return f"{value[:show]}...{value[-show:]}"


# ── models ───────────────────────────────────────────────────────────────────

class SettingsUpdate(BaseModel):
    BOT_TOKEN: Optional[str] = None
    NVD_API_KEY: Optional[str] = None
    ADMIN_IDS: Optional[str] = None
    SCHEDULER_INTERVAL: Optional[int] = None
    RELEASE_TTL: Optional[int] = None
    PRODUCTS_TTL: Optional[int] = None
    CVE_TTL: Optional[int] = None
    MAX_PARALLEL: Optional[int] = None
    RATE_LIMIT_PER_MINUTE: Optional[int] = None
    RATE_LIMIT_PER_HOUR: Optional[int] = None
    NOTIFICATION_ENABLED: Optional[bool] = None
    LOG_LEVEL: Optional[str] = None
    WEB_PASSWORD: Optional[str] = None


# ── routes ────────────────────────────────────────────────────────────────────

@router.get("")
async def get_settings(_: dict = Depends(verify_token)):
    """Return current settings; secrets are masked."""
    env = _read_env()

    def _get(key: str, fallback: str = "") -> str:
        return env.get(key, os.getenv(key, fallback))

    token = _get("BOT_TOKEN")
    nvd = _get("NVD_API_KEY")
    web_pw = _get("WEB_PASSWORD")

    return {
        "BOT_TOKEN_masked": _mask(token, 6),
        "BOT_TOKEN_set": bool(token),
        "NVD_API_KEY_masked": _mask(nvd, 4),
        "NVD_API_KEY_set": bool(nvd),
        "WEB_PASSWORD_set": bool(web_pw),
        "ADMIN_IDS": _get("ADMIN_IDS"),
        "SCHEDULER_INTERVAL": int(_get("SCHEDULER_INTERVAL", "21600")),
        "RELEASE_TTL": int(_get("RELEASE_TTL", "21600")),
        "PRODUCTS_TTL": int(_get("PRODUCTS_TTL", "86400")),
        "CVE_TTL": int(_get("CVE_TTL", "43200")),
        "MAX_PARALLEL": int(_get("MAX_PARALLEL", "15")),
        "RATE_LIMIT_PER_MINUTE": int(_get("RATE_LIMIT_PER_MINUTE", "20")),
        "RATE_LIMIT_PER_HOUR": int(_get("RATE_LIMIT_PER_HOUR", "200")),
        "NOTIFICATION_ENABLED": _get("NOTIFICATION_ENABLED", "true").lower() == "true",
        "LOG_LEVEL": _get("LOG_LEVEL", "INFO"),
        "DATABASE_URL": _get("DATABASE_URL", "sqlite:///./data/bot.db"),
    }


@router.post("")
async def update_settings(body: SettingsUpdate, _: dict = Depends(verify_token)):
    """Write updated settings to .env file."""
    updates: dict[str, str] = {}
    for field, value in body.model_dump(exclude_none=True).items():
        if isinstance(value, bool):
            updates[field] = "true" if value else "false"
        else:
            updates[field] = str(value)

    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    try:
        _write_env(updates)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to write .env: {exc}")

    # Reload os.environ from .env so the running web process sees the new
    # values immediately (e.g. broadcast endpoint picks up the new BOT_TOKEN
    # without needing a web container restart). The bot worker still needs
    # to be restarted via POST /api/bot/restart for its own process to pick
    # them up.
    try:
        load_dotenv(override=True)
    except Exception as exc:
        log.warning("load_dotenv reload failed: %s", exc)

    return {
        "status": "ok",
        "updated": list(updates.keys()),
        "note": "Bot worker must be restarted to apply token/admin-IDs changes.",
    }


@router.post("/test-token")
async def test_bot_token(body: dict, _: dict = Depends(verify_token)):
    """Validate a Telegram bot token against the API."""
    token = body.get("token") or os.getenv("BOT_TOKEN", "")
    if not token:
        raise HTTPException(status_code=400, detail="token is required")

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(
                f"https://api.telegram.org/bot{token}/getMe",
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                data = await resp.json()
                if data.get("ok"):
                    info = data["result"]
                    return {
                        "valid": True,
                        "bot_id": info.get("id"),
                        "bot_username": info.get("username"),
                        "bot_name": info.get("first_name"),
                    }
                return {"valid": False, "error": data.get("description", "Unknown error")}
        except Exception as exc:
            return {"valid": False, "error": str(exc)}


@router.post("/test-nvd")
async def test_nvd_key(body: dict, _: dict = Depends(verify_token)):
    """Check NVD API reachability and key validity."""
    key = body.get("key") or os.getenv("NVD_API_KEY", "")
    headers = {"apiKey": key} if key else {}

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(
                "https://services.nvd.nist.gov/rest/json/cves/2.0?resultsPerPage=1",
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                if resp.status == 200:
                    return {"valid": True, "key_provided": bool(key)}
                if resp.status == 403:
                    return {"valid": False, "error": "Invalid API key (403 Forbidden)"}
                return {"valid": True, "note": f"API reachable, status {resp.status}"}
        except Exception as exc:
            return {"valid": False, "error": str(exc)}
