# --------------------------------------------------------------------------
# auth CRUD method module
#
# @author bnbong bbbong9@gmail.com
# --------------------------------------------------------------------------
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jwt import InvalidTokenError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select as sqlmodel_select

from src.core.config import settings
from src.core.database import get_db
from src.core.passwords import (  # noqa: F401  (re-exported for callers/tests)
    BCRYPT_MAX_PASSWORD_BYTES,
    PasswordTooLongError,
    is_password_length_supported,
    password_byte_length,
    validate_password_length,
)
from src.core.roles import (  # noqa: F401  (re-exported for callers/tests)
    DEFAULT_ROLE,
    ROLE_HIERARCHY,
    SUPER_ADMIN_ROLE,
    VALID_ROLES,
    check_role_permission,
    is_superuser_role,
    is_valid_role,
)
from src.models.users import User

# bandit B105 (false positive): JWT "type" claim values, not credentials.
ACCESS_TOKEN_TYPE = "access"  # nosec B105
REFRESH_TOKEN_TYPE = "refresh"  # nosec B105

# Claims that every token issued by this service must carry. A token without
# all of them is rejected instead of being filled with defaults.
REQUIRED_CLAIMS = ("sub", "user_id", "type", "exp")

# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token")


def _credentials_exception(
    detail: str = "Could not validate credentials",
) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def _password_bytes(password: str) -> bytes:
    return password.encode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its bcrypt hash.

    A candidate that bcrypt cannot hash is simply wrong, so it is rejected
    without raising.
    """
    if not hashed_password:
        return False
    if not is_password_length_supported(plain_password):
        return False
    try:
        return bcrypt.checkpw(
            _password_bytes(plain_password), hashed_password.encode("utf-8")
        )
    except ValueError:
        # Malformed or unsupported hash in the database.
        return False


def get_password_hash(password: str) -> str:
    """Hash a password with bcrypt.

    Raises:
        PasswordTooLongError: If the password is longer than bcrypt supports.
    """
    validate_password_length(password)
    return bcrypt.hashpw(_password_bytes(password), bcrypt.gensalt()).decode("utf-8")


def _encode(payload: Dict[str, Any]) -> str:
    return str(
        jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    )


def create_access_token(
    data: Dict[str, Any], expires_delta: Optional[timedelta] = None
) -> str:
    """Create a JWT access token.

    ``iat``/``exp`` are UTC aware and ``type`` marks the token as an access
    token so that a refresh token can never be presented as a Bearer token.
    """
    now = datetime.now(timezone.utc)
    expire = now + (expires_delta or timedelta(minutes=15))
    to_encode = dict(data)
    to_encode.update({"iat": now, "exp": expire, "type": ACCESS_TOKEN_TYPE})
    return _encode(to_encode)


def create_refresh_token(data: Dict[str, Any]) -> str:
    """Create a JWT refresh token.

    TODO(follow-up): refresh rotation and a server-side revocation store are
    out of scope for this change; a stolen refresh token stays valid until it
    expires.
    """
    now = datetime.now(timezone.utc)
    expire = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode = dict(data)
    to_encode.update({"iat": now, "exp": expire, "type": REFRESH_TOKEN_TYPE})
    return _encode(to_encode)


def decode_token(token: str, expected_type: str) -> Dict[str, Any]:
    """Decode and validate a JWT of the expected type.

    Signature errors, expiry, a missing required claim and a token type
    mismatch are all reported as 401.

    Args:
        token: Raw JWT string.
        expected_type: ``access`` or ``refresh``.

    Returns:
        dict: The decoded claim set.

    Raises:
        HTTPException: 401 when the token cannot be trusted.
    """
    try:
        payload: Dict[str, Any] = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
            options={"require": ["exp"]},
        )
    except InvalidTokenError as exc:
        raise _credentials_exception() from exc

    for claim in REQUIRED_CLAIMS:
        if payload.get(claim) in (None, ""):
            raise _credentials_exception("Token is missing required claims")

    if payload.get("type") != expected_type:
        raise _credentials_exception(f"Invalid token type. Expected '{expected_type}'.")

    return payload


async def get_user(db: AsyncSession, username: str) -> Optional[User]:
    """Get user by username."""
    result = await db.execute(sqlmodel_select(User).where(User.username == username))
    return result.scalar_one_or_none()


async def get_user_by_id(db: AsyncSession, user_id: int) -> Optional[User]:
    """Get user by primary key."""
    result = await db.execute(sqlmodel_select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def authenticate_user(
    db: AsyncSession, username: str, password: str
) -> Optional[User]:
    """Authenticate user with username and password."""
    user = await get_user(db, username)
    if not user:
        return None
    if not verify_password(password, str(user.hashed_password)):
        return None
    return user


async def resolve_token_user(db: AsyncSession, payload: Dict[str, Any]) -> User:
    """Load the user referenced by a validated access token payload.

    The database row is the authority: a revoked, renamed, deactivated or
    demoted account loses access as soon as the row changes, regardless of
    what the token claims.
    """
    user: Optional[User] = None
    raw_user_id = payload.get("user_id")
    if isinstance(raw_user_id, int):
        user = await get_user_by_id(db, raw_user_id)
    elif isinstance(raw_user_id, str) and raw_user_id.isdigit():
        user = await get_user_by_id(db, int(raw_user_id))

    if user is None:
        raise _credentials_exception()

    # The subject must still match the stored username so that a reused
    # user_id cannot inherit another account's token.
    if user.username != payload.get("sub"):
        raise _credentials_exception()

    return user


async def get_current_user(
    token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)
) -> User:
    """Get current user from a JWT access token."""
    payload = decode_token(token, ACCESS_TOKEN_TYPE)
    return await resolve_token_user(db, payload)


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """Get current active user."""
    if not current_user.is_active:
        raise _credentials_exception("Inactive user")
    return current_user


async def verify_token_and_role(
    token: str, required_role: str, db: AsyncSession
) -> Dict[str, Any]:
    """Verify a JWT access token and check the role permission.

    The role claim inside the token is informational only. The effective role
    and the account state are read from the database on every call.

    Args:
        token: JWT access token.
        required_role: Minimum role required.
        db: Database session.

    Returns:
        dict: ``allowed``, ``user_id``, ``username`` and the current ``role``.

    Raises:
        HTTPException: 401 if the token is invalid, 403 on insufficient
            permissions or on an unknown role.
    """
    if not is_valid_role(required_role):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Unknown required role: {required_role}",
        )

    payload = decode_token(token, ACCESS_TOKEN_TYPE)
    user = await resolve_token_user(db, payload)

    if not user.is_active:
        raise _credentials_exception("Inactive user")

    current_role = str(user.role)
    if not is_valid_role(current_role):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Unknown role assigned to user: {current_role}",
        )

    if not check_role_permission(current_role, required_role):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Insufficient permissions. "
                f"Required: {required_role}, Current: {current_role}"
            ),
        )

    return {
        "allowed": True,
        "user_id": user.id,
        "username": user.username,
        "role": current_role,
    }


def require_role(required_role: str) -> Any:
    """Build a dependency that requires at least ``required_role``.

    Args:
        required_role: Minimum role required.

    Returns:
        A FastAPI dependency returning the current user.
    """

    async def dependency(
        current_user: User = Depends(get_current_active_user),
    ) -> User:
        if not check_role_permission(str(current_user.role), required_role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions",
            )
        return current_user

    return dependency
