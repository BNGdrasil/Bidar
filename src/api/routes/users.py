# --------------------------------------------------------------------------
# users CRUD Endpoint
#
# @author bnbong bbbong9@gmail.com
# --------------------------------------------------------------------------
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.crud.auth import get_current_active_user
from src.crud.users import activate_user as crud_activate_user
from src.crud.users import (
    create_user,
)
from src.crud.users import deactivate_user as crud_deactivate_user
from src.crud.users import (
    get_user_by_email,
    get_user_by_username,
    get_users,
)
from src.models.users import User, UserCreate, UserRead
from src.schemas.users import UserRegisterRequest

router = APIRouter()


@router.post("/register", response_model=dict)
async def register_user(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Register a new user."""
    # Check if user already exists
    if await get_user_by_username(db, user_data.username):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered",
        )

    if await get_user_by_email(db, user_data.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered"
        )

    # Create new user
    user = await create_user(db, user_data)

    return {
        "message": "User registered successfully",
        "user_id": user.id,
        "username": user.username,
        "email": user.email,
    }


@router.get("/users", response_model=List[UserRead])
async def list_users(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> List[UserRead]:
    """List all users (superuser only)"""
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions"
        )

    users = await get_users(db)

    return [
        UserRead(
            id=user.id,
            username=user.username,
            email=user.email,
            full_name=user.full_name,
            is_active=user.is_active,
            is_superuser=user.is_superuser,
            created_at=user.created_at,
        )
        for user in users
    ]


@router.put("/users/{user_id}/activate")
async def activate_user(
    user_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Activate a user (superuser only)"""
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions"
        )

    user = await crud_activate_user(db, user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    return {"message": f"User {user.username} activated successfully"}


@router.put("/users/{user_id}/deactivate")
async def deactivate_user(
    user_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Deactivate a user (superuser only)"""
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions"
        )

    user = await crud_deactivate_user(db, user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    return {"message": f"User {user.username} deactivated successfully"}
