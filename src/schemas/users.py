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
    UserAdminUpdate,
    UserBase,
    UserCreate,
    UserRead,
    UserRegisterRequest,
    UserUpdate,
)

# Alias for compatibility
UserResponse = UserRead

__all__ = [
    "UserBase",
    "User",
    "UserCreate",
    "UserRead",
    "UserUpdate",
    "UserAdminUpdate",
    "UserRegisterRequest",
    "UserResponse",
    "APIKeyBase",
    "APIKey",
    "APIKeyCreate",
    "APIKeyRead",
]
