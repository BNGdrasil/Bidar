# --------------------------------------------------------------------------
# users schema module
#
# @author bnbong bbbong9@gmail.com
# --------------------------------------------------------------------------
from src.models.users import (
    APIKey,
    APIKeyBase,
    APIKeyCreate,
    APIKeyRead,
    User,
    UserBase,
    UserCreate,
    UserRead,
    UserUpdate,
)

# Alias for compatibility
UserRegisterRequest = UserCreate
UserResponse = UserRead

__all__ = [
    "UserBase",
    "User",
    "UserCreate",
    "UserRead",
    "UserUpdate",
    "UserRegisterRequest",
    "UserResponse",
    "APIKeyBase",
    "APIKey",
    "APIKeyCreate",
    "APIKeyRead",
]
