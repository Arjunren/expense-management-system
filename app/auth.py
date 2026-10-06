from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Annotated
from uuid import uuid4

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pwdlib import PasswordHash
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import AuthSession, Role, User

password_hash = PasswordHash.recommended()
dummy_hash = password_hash.hash("not-a-real-user-password")
bearer = HTTPBearer(auto_error=False)
_attempts: dict[str, deque[datetime]] = defaultdict(deque)
_lock = Lock()


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return password_hash.verify(password, hashed)


def check_login_rate(request: Request) -> None:
    key = request.client.host if request.client else "unknown"
    now = datetime.now(timezone.utc)
    with _lock:
        values = _attempts[key]
        while values and values[0] < now - timedelta(minutes=1):
            values.popleft()
        if len(values) >= 10:
            raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many login attempts")
        values.append(now)


def issue_token(db: Session, user: User) -> str:
    settings, now = get_settings(), datetime.now(timezone.utc)
    expires, token_id = now + timedelta(minutes=settings.jwt_expiry_minutes), str(uuid4())
    db.add(AuthSession(id=token_id, user_id=user.id, expires_at=expires))
    db.commit()
    return jwt.encode({"sub": str(user.id), "jti": token_id, "iat": now, "exp": expires}, settings.jwt_secret, algorithm="HS256")


def get_current_user(credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)], db: Annotated[Session, Depends(get_db)]) -> User:
    error = HTTPException(status.HTTP_401_UNAUTHORIZED, "A valid bearer token is required")
    if credentials is None:
        raise error
    try:
        payload = jwt.decode(credentials.credentials, get_settings().jwt_secret, algorithms=["HS256"])
        user_id, token_id = int(payload["sub"]), str(payload["jti"])
    except (jwt.PyJWTError, KeyError, TypeError, ValueError):
        raise error from None
    active = db.scalar(select(AuthSession.id).join(User, User.id == AuthSession.user_id).where(AuthSession.id == token_id, AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None), AuthSession.expires_at > datetime.now(timezone.utc), User.is_active.is_(True)))
    user = db.get(User, user_id)
    if active is None or user is None:
        raise error
    return user


def revoke_token(db: Session, token: str) -> None:
    try:
        token_id = str(jwt.decode(token, get_settings().jwt_secret, algorithms=["HS256"])["jti"])
    except (jwt.PyJWTError, KeyError, TypeError):
        return
    record = db.get(AuthSession, token_id)
    if record and record.revoked_at is None:
        record.revoked_at = datetime.now(timezone.utc)
        db.commit()


def require_roles(*roles: Role):
    def dependency(user: Annotated[User, Depends(get_current_user)]) -> User:
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient permissions")
        return user
    return dependency

