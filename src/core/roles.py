# --------------------------------------------------------------------------
# Role definitions shared by models, CRUD and API layers
#
# This module must not import from src.models or src.crud so that it can be
# used by every layer without creating an import cycle.
#
# @author bnbong bbbong9@gmail.com
# --------------------------------------------------------------------------
from typing import Dict, Tuple

# Role is the single source of truth for authorization. ``User.is_superuser``
# is a derived column kept for backwards compatibility with existing rows and
# external consumers.
ROLE_HIERARCHY: Dict[str, int] = {
    "user": 0,
    "moderator": 1,
    "admin": 2,
    "super_admin": 3,
}

SUPER_ADMIN_ROLE = "super_admin"
ADMIN_ROLE = "admin"
MODERATOR_ROLE = "moderator"
DEFAULT_ROLE = "user"

VALID_ROLES: Tuple[str, ...] = tuple(ROLE_HIERARCHY)


def is_valid_role(role: str) -> bool:
    """Return True when the given role name is known."""
    return role in ROLE_HIERARCHY


def normalize_role(role: str) -> str:
    """Validate and return a role name.

    Raises:
        ValueError: If the role is not part of the known hierarchy.
    """
    if not is_valid_role(role):
        raise ValueError(
            f"Invalid role '{role}'. Allowed roles: {', '.join(VALID_ROLES)}"
        )
    return role


def is_superuser_role(role: str) -> bool:
    """Return True when the role implies the legacy ``is_superuser`` flag."""
    return role == SUPER_ADMIN_ROLE


def check_role_permission(user_role: str, required_role: str) -> bool:
    """Check if a user role satisfies the required role.

    Unknown roles are rejected on both sides instead of silently falling back
    to the lowest level.

    Args:
        user_role: The role of the user.
        required_role: The minimum role required.

    Returns:
        bool: True if the user role is known and at least as high as required.
    """
    if not is_valid_role(user_role) or not is_valid_role(required_role):
        return False
    return ROLE_HIERARCHY[user_role] >= ROLE_HIERARCHY[required_role]
