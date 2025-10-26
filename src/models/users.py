# --------------------------------------------------------------------------
# users model module
#
# @author bnbong bbbong9@gmail.com
# --------------------------------------------------------------------------
from datetime import datetime
from typing import Optional

from sqlalchemy import Column, DateTime, func, text
from sqlmodel import Field, SQLModel


class UserBase(SQLModel):
    """Base User model with shared fields."""

    username: str = Field(max_length=50, unique=True, index=True)
    email: str = Field(max_length=100, unique=True, index=True)
    full_name: Optional[str] = Field(default=None, max_length=100)
    is_active: bool = Field(default=True)
    is_superuser: bool = Field(default=False)
    role: str = Field(
        default="user", max_length=20
    )  # user, moderator, admin, super_admin


class User(UserBase, table=True):
    """User database model."""

    __tablename__ = "users"

    id: Optional[int] = Field(default=None, primary_key=True)
    hashed_password: str = Field(max_length=255)
    created_at: Optional[datetime] = Field(
        default=None, sa_column=Column(DateTime, server_default=func.now())
    )
    updated_at: Optional[datetime] = Field(
        default=None, sa_column=Column(DateTime, onupdate=func.now())
    )

    def __repr__(self) -> str:
        """Return string representation of User."""
        return f"<User(id={self.id}, username='{self.username}', email='{self.email}')>"


class UserCreate(UserBase):
    """User creation model."""

    password: str


class UserRead(UserBase):
    """User read model."""

    id: int
    created_at: Optional[datetime] = None


class UserUpdate(SQLModel):
    """User update model."""

    username: Optional[str] = Field(default=None, max_length=50)
    email: Optional[str] = Field(default=None, max_length=100)
    full_name: Optional[str] = Field(default=None, max_length=100)
    is_active: Optional[bool] = None
    is_superuser: Optional[bool] = None
    role: Optional[str] = Field(default=None, max_length=20)


class APIKeyBase(SQLModel):
    """Base API Key model with shared fields."""

    key_name: str = Field(max_length=100)
    user_id: int
    is_active: bool = Field(default=True)


class APIKey(APIKeyBase, table=True):
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
        return f"<APIKey(id={self.id}, key_name='{self.key_name}', user_id={self.user_id})>"


class APIKeyCreate(APIKeyBase):
    """API Key creation model."""

    pass


class APIKeyRead(APIKeyBase):
    """API Key read model."""

    id: int
    created_at: Optional[datetime] = None
    last_used_at: Optional[datetime] = None
