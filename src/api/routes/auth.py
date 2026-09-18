# --------------------------------------------------------------------------
# auth CRUD Endpoint
#
# @author bnbong bbbong9@gmail.com
# --------------------------------------------------------------------------
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.core.database import get_db
from src.core.ratelimit import login_limiter
from src.crud.auth import (
    REFRESH_TOKEN_TYPE,
    authenticate_user,
    create_access_token,
    create_refresh_token,
    decode_token,
    get_current_active_user,
    resolve_token_user,
)
from src.models.users import User, UserRead
from src.schemas.auth import RefreshTokenRequest, TokenResponse

router = APIRouter()


def _token_payload(user: User) -> dict:
    return {
        "sub": user.username,
        "user_id": user.id,
        "role": user.role,
    }


def _inactive_account_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Inactive user",
        headers={"WWW-Authenticate": "Bearer"},
    )


@router.post("/token", response_model=TokenResponse)
async def login_for_access_token(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Login and get an access token."""
    # request.client.host is the real caller only when uvicorn is started
    # with proxy_headers and a matching FORWARDED_ALLOW_IPS. Forwarding
    # headers are deliberately not parsed here: that would let any client
    # pick its own limiter key.
    client_key = request.client.host if request.client else "unknown"
    if not login_limiter.hit(client_key, settings.LOGIN_RATE_LIMIT_PER_MINUTE):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Try again later.",
        )

    user = await authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise _inactive_account_error()

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data=_token_payload(user), expires_delta=access_token_expires
    )
    refresh_token = create_refresh_token(data=_token_payload(user))

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        # bandit B106 (false positive): OAuth2 token_type literal, not a credential.
        token_type="bearer",  # nosec B106
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_access_token(
    request: RefreshTokenRequest, db: AsyncSession = Depends(get_db)
) -> TokenResponse:
    """Refresh an access token using a refresh token.

    TODO(follow-up): rotate the refresh token and keep a server-side
    revocation store; both are out of scope for this change.
    """
    payload = decode_token(request.refresh_token, REFRESH_TOKEN_TYPE)
    user = await resolve_token_user(db, payload)

    if not user.is_active:
        raise _inactive_account_error()

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data=_token_payload(user), expires_delta=access_token_expires
    )

    return TokenResponse(
        access_token=access_token,
        # bandit B106 (false positive): OAuth2 token_type literal, not a credential.
        token_type="bearer",  # nosec B106
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.get("/me", response_model=UserRead)
async def read_users_me(
    current_user: User = Depends(get_current_active_user),
) -> UserRead:
    """Get current user information."""
    return UserRead(
        id=int(current_user.id) if current_user.id is not None else 0,
        username=current_user.username,
        email=current_user.email,
        full_name=current_user.full_name,
        is_active=current_user.is_active,
        is_superuser=current_user.is_superuser,
        role=current_user.role,
        created_at=current_user.created_at,
    )
