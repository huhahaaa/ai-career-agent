from typing import Callable, Optional, Tuple

from fastapi import Depends, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.exceptions import AppException
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.user import User


oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/v1/auth/login",
    auto_error=False,
)


def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    if not token:
        raise AppException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code=40102,
            message="authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = decode_access_token(token)
        user_id = int(payload["sub"])
    except (KeyError, TypeError, ValueError):
        raise AppException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code=40102,
            message="invalid or expired access token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise AppException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code=40103,
            message="user is inactive or no longer exists",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def require_roles(*allowed_roles: str) -> Callable[..., User]:
    roles: Tuple[str, ...] = tuple(allowed_roles)

    def role_dependency(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise AppException(
                status_code=status.HTTP_403_FORBIDDEN,
                code=40301,
                message="insufficient permissions",
            )
        return current_user

    return role_dependency
