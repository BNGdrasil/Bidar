# --------------------------------------------------------------------------
# rbac routes module - Role-Based Access Control API
#
# @author bnbong bbbong9@gmail.com
# --------------------------------------------------------------------------
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.crud.auth import get_current_active_user, verify_token_and_role
from src.models.users import User

router = APIRouter(prefix="/rbac", tags=["rbac"])

BEARER_PREFIX = "Bearer "


class VerifyPermissionRequest(BaseModel):
    """Request model for permission verification."""

    required_role: str


class VerifyPermissionResponse(BaseModel):
    """Response model for permission verification."""

    allowed: bool
    user_id: Optional[int] = None
    username: Optional[str] = None
    role: str


@router.post("/verify-permission", response_model=VerifyPermissionResponse)
async def verify_permission(
    request: VerifyPermissionRequest,
    authorization: Annotated[Optional[str], Header()] = None,
    db: AsyncSession = Depends(get_db),
) -> VerifyPermissionResponse:
    """Verify user permission based on the current role stored in the database.

    Used by Bifrost Gateway to check if a user has sufficient permissions to
    access admin APIs. Only access tokens are accepted, and the role is read
    from the database rather than from the token claims.

    Args:
        request: Contains required_role.
        authorization: JWT access token in the Authorization header.
        db: Database session.

    Returns:
        VerifyPermissionResponse: Permission verification result.

    Raises:
        HTTPException: 401 if unauthorized, 403 if forbidden.
    """
    if not authorization or not authorization.startswith(BEARER_PREFIX):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = authorization[len(BEARER_PREFIX) :].strip()

    result = await verify_token_and_role(token, request.required_role, db)
    return VerifyPermissionResponse(**result)


@router.get("/my-role")
async def get_my_role(
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> dict:
    """Get current user's role information.

    Args:
        current_user: Current authenticated user.

    Returns:
        dict: User's role information.
    """
    return {
        "user_id": current_user.id,
        "username": current_user.username,
        "role": current_user.role,
        "is_superuser": current_user.is_superuser,
    }
