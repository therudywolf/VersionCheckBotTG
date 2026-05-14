"""
VersionCheckBot Web Panel — Authentication

SPDX-License-Identifier: AGPL-3.0-or-later
Copyright (c) 2024 VersionCheckBot Contributors
"""
import os
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


def _secret_key() -> str:
    key = os.getenv("WEB_SECRET_KEY", "")
    if not key:
        # Derive from BOT_TOKEN so it's stable without extra config
        token = os.getenv("BOT_TOKEN", "fallback-insecure-key")
        key = f"vcb-web-{token[:20]}"
    return key


def get_web_password() -> str:
    return os.getenv("WEB_PASSWORD", "admin")


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
