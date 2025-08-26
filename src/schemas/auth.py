# --------------------------------------------------------------------------
# auth schema module
#
# @author bnbong bbbong9@gmail.com
# --------------------------------------------------------------------------
from typing import Optional

from sqlmodel import SQLModel


class TokenData(SQLModel):
    """Token data model."""

    username: Optional[str] = None


class Token(SQLModel):
    """Token response model."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class LoginRequest(SQLModel):
    """Login request model."""

    username: str
    password: str


class RefreshTokenRequest(SQLModel):
    """Refresh token request model."""

    refresh_token: str


class TokenResponse(SQLModel):
    """Token response model."""

    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "bearer"
    expires_in: Optional[int] = None


# Alias for compatibility
authBase = SQLModel
authResponse = TokenResponse

__all__ = [
    "TokenData",
    "Token",
    "LoginRequest",
    "RefreshTokenRequest",
    "TokenResponse",
    "authBase",
    "authResponse",
]
