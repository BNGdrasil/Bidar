# --------------------------------------------------------------------------
# rbac routes module - Role-Based Access Control API
#
# @author bnbong bbbong9@gmail.com
# --------------------------------------------------------------------------
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel

from src.crud.auth import get_current_active_user, verify_token_and_role
from src.models.users import User

router = APIRouter(prefix="/rbac", tags=["rbac"])


class VerifyPermissionRequest(BaseModel):
    """Request model for permission verification."""

    required_role: str


class VerifyPermissionResponse(BaseModel):
    """Response model for permission verification."""

    allowed: bool
    user_id: int | None = None
    username: str | None = None
    role: str


@router.post("/verify-permission", response_model=VerifyPermissionResponse)
async def verify_permission(
    request: VerifyPermissionRequest,
    authorization: Annotated[str | None, Header()] = None,
) -> VerifyPermissionResponse:
    """Verify user permission based on role.

    Used by Bifrost Gateway to check if user has sufficient permissions
    to access admin APIs.

    Args:
        request: Contains required_role
        authorization: JWT token in Authorization header (Bearer token)

    Returns:
        VerifyPermissionResponse: Permission verification result

    Raises:
        HTTPException: 401 if unauthorized, 403 if forbidden
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = authorization.replace("Bearer ", "")

    try:
        result = await verify_token_and_role(token, request.required_role)
        return VerifyPermissionResponse(**result)
    except HTTPException:
        # Re-raise HTTP exceptions from verify_token_and_role
        raise


@router.get("/my-role")
async def get_my_role(
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> dict:
    """Get current user's role information.

    Args:
        current_user: Current authenticated user

    Returns:
        dict: User's role information
    """
    return {
        "user_id": current_user.id,
        "username": current_user.username,
        "role": current_user.role,
        "is_superuser": current_user.is_superuser,
    }
