from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import bcrypt
from jose import JWTError, jwt

from app.core.config import settings


def hash_password(password: str) -> str:
    encoded_password = password.encode("utf-8")
    if len(encoded_password) > 72:
        raise ValueError("password must not exceed 72 bytes")
    return bcrypt.hashpw(encoded_password, bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(
            password.encode("utf-8"),
            hashed_password.encode("utf-8"),
        )
    except (TypeError, ValueError):
        return False


def create_access_token(
    subject: Any,
    extra_claims: Optional[Dict[str, Any]] = None,
) -> str:
    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=settings.access_token_expire_minutes
    )
    payload: Dict[str, Any] = {
        "sub": str(subject),
        "exp": expires_at,
        "type": "access",
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(
        payload,
        settings.secret_key,
        algorithm=settings.jwt_algorithm,
    )


def decode_access_token(token: str) -> Dict[str, Any]:
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.jwt_algorithm],
        )
    except JWTError as exc:
        raise ValueError("invalid or expired access token") from exc
    if payload.get("type") != "access" or not payload.get("sub"):
        raise ValueError("invalid access token payload")
    return payload
