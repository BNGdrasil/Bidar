# --------------------------------------------------------------------------
# users model module
#
# @author bnbong bbbong9@gmail.com
# --------------------------------------------------------------------------
from datetime import datetime
from typing import Optional

from pydantic import field_validator
from sqlalchemy import Column, DateTime, func
from sqlmodel import Field, SQLModel

from src.core.passwords import (
    BCRYPT_MAX_PASSWORD_BYTES,
    MIN_PASSWORD_LENGTH,
    is_password_length_supported,
)
from src.core.roles import DEFAULT_ROLE, VALID_ROLES, normalize_role


def _check_password_bytes(value: str) -> str:
    """Reject a password bcrypt would have to truncate.

    The declared max_length is in characters; bcrypt's limit is 72 bytes, so
    a shorter non-ASCII password can still be too long.
    """
    if not is_password_length_supported(value):
        raise ValueError(
            "Password must be at most "
            f"{BCRYPT_MAX_PASSWORD_BYTES} bytes when encoded as UTF-8. "
            "Non-ASCII characters take more than one byte each."
        )
    return value


class UserBase(SQLModel):
    """Base User model with the non-privileged shared fields.

    Privileged fields (``is_active``, ``is_superuser``, ``role``) are declared
    on the table model and on the admin-facing input models only, so that they
    can never be bound from an untrusted request body.
    """

    username: str = Field(max_length=50, unique=True, index=True)
    email: str = Field(max_length=100, unique=True, index=True)
    full_name: Optional[str] = Field(default=None, max_length=100)


class User(UserBase, table=True):  # type: ignore[call-arg, unused-ignore]
    """User database model."""

    __tablename__ = "users"

    id: Optional[int] = Field(default=None, primary_key=True)
    hashed_password: str = Field(max_length=255)
    is_active: bool = Field(default=True)
    # Derived from ``role``; kept as a column for existing rows and for
    # external consumers that still read it.
    is_superuser: bool = Field(default=False)
    role: str = Field(
        default=DEFAULT_ROLE, max_length=20
    )  # user, moderator, admin, super_admin
    created_at: Optional[datetime] = Field(
        default=None, sa_column=Column(DateTime, server_default=func.now())
    )
    updated_at: Optional[datetime] = Field(
        default=None, sa_column=Column(DateTime, onupdate=func.now())
    )

    def __repr__(self) -> str:
        """Return string representation of User."""
        return f"<User(id={self.id}, username='{self.username}', email='{self.email}')>"


class UserRegisterRequest(UserBase):
    """Public self-service registration payload.

    No route is bound to this schema at the moment: public registration is
    closed and accounts are created by a super admin or by the create-admin
    CLI. The schema is kept so that a future approved signup flow starts from
    a payload that cannot carry privileged fields.
    """

    model_config = {"extra": "forbid"}

    password: str = Field(min_length=MIN_PASSWORD_LENGTH, max_length=128)

    @field_validator("password")
    @classmethod
    def _validate_password(cls, value: str) -> str:
        return _check_password_bytes(value)


class UserCreate(UserBase):
    """Administrative user creation model.

    ``role`` may be set here because the endpoint using it requires a super
    admin. ``is_superuser`` is never accepted as input; it is derived from
    ``role``.
    """

    password: str = Field(min_length=MIN_PASSWORD_LENGTH, max_length=128)
    role: str = Field(default=DEFAULT_ROLE, max_length=20)
    is_active: bool = Field(default=True)

    @field_validator("password")
    @classmethod
    def _validate_password(cls, value: str) -> str:
        return _check_password_bytes(value)

    @field_validator("role")
    @classmethod
    def _validate_role(cls, value: str) -> str:
        return normalize_role(value)


class UserRead(UserBase):
    """User read model."""

    id: int
    is_active: bool = True
    is_superuser: bool = False
    role: str = DEFAULT_ROLE
    created_at: Optional[datetime] = None


class UserUpdate(SQLModel):
    """User update model.

    ``is_superuser`` is not accepted; it follows ``role``.
    """

    username: Optional[str] = Field(default=None, max_length=50)
    email: Optional[str] = Field(default=None, max_length=100)
    full_name: Optional[str] = Field(default=None, max_length=100)
    is_active: Optional[bool] = None
    role: Optional[str] = Field(default=None, max_length=20)

    @field_validator("role")
    @classmethod
    def _validate_role(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        return normalize_role(value)


class UserAdminUpdate(SQLModel):
    """Administrative user update payload.

    ``username`` and ``email`` are identity fields and are not editable
    through this endpoint. ``is_superuser`` is not accepted either; it follows
    ``role``.
    """

    model_config = {"extra": "forbid"}

    full_name: Optional[str] = Field(default=None, max_length=100)
    role: Optional[str] = Field(default=None, max_length=20)
    is_active: Optional[bool] = None

    @field_validator("role")
    @classmethod
    def _validate_role(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        return normalize_role(value)


class APIKeyBase(SQLModel):
    """Base API Key model with shared fields."""

    key_name: str = Field(max_length=100)
    user_id: int
    is_active: bool = Field(default=True)


class APIKey(APIKeyBase, table=True):  # type: ignore[call-arg, unused-ignore]
    """API Key database model for service authentication."""

    __tablename__ = "api_keys"

    id: Optional[int] = Field(default=None, primary_key=True)
    key_hash: str = Field(max_length=255)
    created_at: Optional[datetime] = Field(
        default=None, sa_column=Column(DateTime, server_default=func.now())
    )
    last_used_at: Optional[datetime] = None

    def __repr__(self) -> str:
        """Return string representation of APIKey."""
        return (
            f"<APIKey(id={self.id}, key_name='{self.key_name}', "
            f"user_id={self.user_id})>"
        )


class APIKeyCreate(APIKeyBase):
    """API Key creation model."""

    pass


class APIKeyRead(APIKeyBase):
    """API Key read model."""

    id: int
    created_at: Optional[datetime] = None
    last_used_at: Optional[datetime] = None


__all__ = [
    "VALID_ROLES",
    "UserBase",
    "User",
    "UserRegisterRequest",
    "UserCreate",
    "UserRead",
    "UserUpdate",
    "UserAdminUpdate",
    "APIKeyBase",
    "APIKey",
    "APIKeyCreate",
    "APIKeyRead",
]
