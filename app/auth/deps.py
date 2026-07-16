"""
auth/deps.py — FastAPI dependencies for authentication and role gating.

`get_current_user` validates the bearer access token and loads the user row.
`require_role(...)` builds a dependency that additionally enforces the user's role,
used to keep, e.g., processing endpoints for processors and farm endpoints for
farmers/officers.
"""
from __future__ import annotations

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from db import get_db
from models import User, UserRole
from auth.security import decode_token

# auto_error=False so we can return a 401 with a consistent message/headers.
_bearer = HTTPBearer(auto_error=False)

_CREDENTIALS_EXC = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Not authenticated",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None or not credentials.credentials:
        raise _CREDENTIALS_EXC
    try:
        payload = decode_token(credentials.credentials, expected_type="access")
    except (jwt.PyJWTError, ValueError):
        raise _CREDENTIALS_EXC

    user_id = payload.get("sub")
    if not user_id:
        raise _CREDENTIALS_EXC

    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise _CREDENTIALS_EXC
    return user


def require_role(*roles: UserRole):
    """Dependency factory: allow only users whose role is in `roles`."""

    allowed = set(roles)

    def _dep(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your account type does not have access to this resource.",
            )
        return user

    return _dep
