from fastapi import APIRouter, Depends, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.config import settings
from app.core.exceptions import AppException
from app.core.security import create_access_token, hash_password, verify_password
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserOut
from app.schemas.common import ApiResponse, success_response

router = APIRouter()


@router.post(
    "/register",
    response_model=ApiResponse[UserOut],
    status_code=status.HTTP_201_CREATED,
)
def register(
    payload: RegisterRequest,
    db: Session = Depends(get_db),
) -> ApiResponse[UserOut]:
    existing_user = db.scalar(
        select(User).where(
            or_(
                User.username == payload.username,
                User.email == str(payload.email),
            )
        )
    )
    if existing_user:
        field_name = (
            "username" if existing_user.username == payload.username else "email"
        )
        raise AppException(
            status_code=status.HTTP_409_CONFLICT,
            code=40901 if field_name == "username" else 40902,
            message="%s already exists" % field_name,
        )

    try:
        hashed_password = hash_password(payload.password)
    except ValueError as exc:
        raise AppException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code=42201,
            message=str(exc),
        )

    user = User(
        username=payload.username,
        email=str(payload.email),
        hashed_password=hashed_password,
        role="student",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return success_response(
        UserOut.model_validate(user),
        message="registered successfully",
    )


@router.post("/login", response_model=ApiResponse[TokenResponse])
def login(
    payload: LoginRequest,
    db: Session = Depends(get_db),
) -> ApiResponse[TokenResponse]:
    user = db.scalar(select(User).where(User.username == payload.username))
    if user is None or not verify_password(payload.password, user.hashed_password):
        raise AppException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code=40101,
            message="incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise AppException(
            status_code=status.HTTP_403_FORBIDDEN,
            code=40302,
            message="user account is inactive",
        )

    access_token = create_access_token(
        subject=user.id,
        extra_claims={"role": user.role},
    )
    return success_response(
        TokenResponse(
            access_token=access_token,
            expires_in=settings.access_token_expire_minutes * 60,
            user=UserOut.model_validate(user),
        ),
        message="logged in successfully",
    )


@router.post("/logout", response_model=ApiResponse[None])
def logout(_current_user: User = Depends(get_current_user)) -> ApiResponse[None]:
    return success_response(message="logged out")


@router.get("/me", response_model=ApiResponse[UserOut])
def read_current_user(
    current_user: User = Depends(get_current_user),
) -> ApiResponse[UserOut]:
    return success_response(UserOut.model_validate(current_user))
