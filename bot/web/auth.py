"""
VersionCheckBot Web Panel — Authentication

SPDX-License-Identifier: AGPL-3.0-or-later
Copyright (c) 2024 VersionCheckBot Contributors
"""
import os
import secrets
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

log = logging.getLogger(__name__)

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24

security = HTTPBearer(auto_error=False)

# Process-lifetime random key used only as a last resort.
# When this is used, tokens are invalidated on every restart — by design.
_EPHEMERAL_KEY = secrets.token_hex(32)
_warned_secret = False
_warned_password = False


def _secret_key() -> str:
    """Resolve the JWT signing key.

    Priority:
      1. WEB_SECRET_KEY (required for stable tokens across restarts)
      2. Derived from BOT_TOKEN (stable if BOT_TOKEN doesn't change)
      3. Ephemeral random key + loud warning (tokens die on restart)
    """
    global _warned_secret
    key = os.getenv("WEB_SECRET_KEY", "").strip()
    if key:
        return key
    token = os.getenv("BOT_TOKEN", "").strip()
    if token:
        return f"vcb-web-{token}"
    if not _warned_secret:
        log.warning(
            "WEB_SECRET_KEY and BOT_TOKEN both unset — using ephemeral key. "
            "Web tokens will become invalid on every restart."
        )
        _warned_secret = True
    return _EPHEMERAL_KEY


def get_web_password() -> str:
    """Return the configured admin password.

    Defaults to "admin" with a loud warning. In production, set WEB_PASSWORD.
    """
    global _warned_password
    pw = os.getenv("WEB_PASSWORD", "").strip()
    if pw:
        return pw
    if not _warned_password:
        log.warning(
            "WEB_PASSWORD not set — falling back to 'admin'. "
            "Set WEB_PASSWORD in .env before exposing the panel."
        )
        _warned_password = True
    return "admin"


def create_access_token(expires_hours: int = ACCESS_TOKEN_EXPIRE_HOURS) -> str:
    payload = {
        "sub": "admin",
        "exp": datetime.now(timezone.utc) + timedelta(hours=expires_hours),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, _secret_key(), algorithm=ALGORITHM)


def verify_token(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> dict:
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = jwt.decode(
            credentials.credentials, _secret_key(), algorithms=[ALGORITHM]
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )
