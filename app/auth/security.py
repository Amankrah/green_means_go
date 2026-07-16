"""
auth/security.py — password hashing and JWT encode/decode.

Passwords are hashed with bcrypt (via the `bcrypt` package directly, no passlib).
Tokens are signed JWTs: a short-lived access token carried in the Authorization
header, and a longer-lived refresh token exchanged at /auth/refresh for a new access
token. Both encode the user id (`sub`), the role, and a `type` claim so a refresh
token can't be used as an access token.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import bcrypt
import jwt

# Signing config. JWT_SECRET MUST be set in production; the dev fallback is obviously
# not secret and only exists so local runs work out of the box.
JWT_SECRET = os.getenv("JWT_SECRET", "dev-insecure-change-me")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_TTL_MIN = int(os.getenv("ACCESS_TOKEN_TTL_MIN", "30"))
REFRESH_TOKEN_TTL_DAYS = int(os.getenv("REFRESH_TOKEN_TTL_DAYS", "14"))


# --- passwords -------------------------------------------------------------------

def hash_password(plain: str) -> str:
    # bcrypt truncates at 72 bytes; encode and hash. Store the utf-8 hash string.
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


# --- tokens ----------------------------------------------------------------------

def _encode(sub: str, role: str, token_type: str, ttl: timedelta) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": sub,
        "role": role,
        "type": token_type,
        "iat": now,
        "exp": now + ttl,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def create_access_token(user_id: str, role: str) -> str:
    return _encode(user_id, role, "access", timedelta(minutes=ACCESS_TOKEN_TTL_MIN))


def create_refresh_token(user_id: str, role: str) -> str:
    return _encode(user_id, role, "refresh", timedelta(days=REFRESH_TOKEN_TTL_DAYS))


def decode_token(token: str, expected_type: Optional[str] = None) -> dict[str, Any]:
    """Decode and validate a token. Raises jwt.PyJWTError on bad signature/expiry, and
    ValueError if the token is not of the expected type."""
    payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    if expected_type is not None and payload.get("type") != expected_type:
        raise ValueError(f"expected a {expected_type} token")
    return payload
