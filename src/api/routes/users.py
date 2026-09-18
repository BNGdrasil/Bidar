# --------------------------------------------------------------------------
# users CRUD Endpoint
#
# Public self-service registration is closed. Accounts are created either by a
# super admin through POST /users or by the create-admin CLI.
#
# @author bnbong bbbong9@gmail.com
# --------------------------------------------------------------------------
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.core.roles import ADMIN_ROLE, SUPER_ADMIN_ROLE, check_role_permission
from src.crud.auth import require_role
from src.crud.users import (
    LastSuperAdminError,
)
from src.crud.users import activate_user as crud_activate_user
from src.crud.users import create_user
from src.crud.users import deactivate_user as crud_deactivate_user
from src.crud.users import delete_user as crud_delete_user
from src.crud.users import (
    get_user_by_email,
    get_user_by_id,
    get_user_by_username,
    get_users,
)
from src.crud.users import update_user as crud_update_user
from src.models.users import User, UserAdminUpdate, UserCreate, UserRead, UserUpdate

router = APIRouter()


def _last_super_admin_conflict(exc: LastSuperAdminError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


async def _load_target(db: AsyncSession, user_id: int) -> User:
    user = await get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    return user


def _assert_may_manage(actor: User, target: User) -> None:
    """Refuse an admin acting on an account at admin level or above.

    Without this an admin could deactivate a super admin, or deactivate a peer
    admin, and so escalate by removing the accounts that could undo the
    change. Super admins are exempt; the last-super-admin guard still applies
    to them.
    """
    if check_role_permission(str(actor.role), SUPER_ADMIN_ROLE):
        return
    if check_role_permission(str(target.role), ADMIN_ROLE):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only a super admin can manage an admin account",
        )


def _to_read_model(user: User) -> UserRead:
    return UserRead(
        id=int(user.id) if user.id is not None else 0,
        username=user.username,
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active,
        is_superuser=user.is_superuser,
        role=user.role,
        created_at=user.created_at,
    )


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def create_user_as_admin(
    user_data: UserCreate,
    current_user: User = Depends(require_role(SUPER_ADMIN_ROLE)),
    db: AsyncSession = Depends(get_db),
) -> UserRead:
    """Create a user (super admin only).

    This replaces the former public POST /users/register endpoint.
    """
    if await get_user_by_username(db, user_data.username):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered",
        )

    if await get_user_by_email(db, user_data.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered"
        )

    user = await create_user(db, user_data)
    return _to_read_model(user)


@router.get("/users", response_model=List[UserRead])
async def list_users(
    current_user: User = Depends(require_role(ADMIN_ROLE)),
    db: AsyncSession = Depends(get_db),
) -> List[UserRead]:
    """List all users (admin and above)."""
    users = await get_users(db)
    return [_to_read_model(user) for user in users]


@router.get("/users/{user_id}", response_model=UserRead)
async def get_user(
    user_id: int,
    current_user: User = Depends(require_role(ADMIN_ROLE)),
    db: AsyncSession = Depends(get_db),
) -> UserRead:
    """Get a single user by id (admin and above)."""
    user = await get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    return _to_read_model(user)


@router.patch("/users/{user_id}", response_model=UserRead)
async def update_user(
    user_id: int,
    user_update: UserAdminUpdate,
    current_user: User = Depends(require_role(SUPER_ADMIN_ROLE)),
    db: AsyncSession = Depends(get_db),
) -> UserRead:
    """Update a user's profile, role or active state (super admin only).

    ``username`` and ``email`` are not editable here, and ``is_superuser`` is
    derived from ``role``.
    """
    # Only the fields the caller actually sent are forwarded, so an omitted
    # field is left untouched rather than reset to its default.
    changes = UserUpdate.model_validate(user_update.model_dump(exclude_unset=True))

    try:
        user = await crud_update_user(db, user_id, changes)
    except LastSuperAdminError as exc:
        raise _last_super_admin_conflict(exc) from exc

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    return _to_read_model(user)


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int,
    current_user: User = Depends(require_role(SUPER_ADMIN_ROLE)),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Delete a user (super admin only).

    Deleting your own account is refused before the last-super-admin guard
    runs, so the answer does not depend on how many other super admins exist.
    """
    if current_user.id == user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot delete your own account",
        )

    try:
        deleted = await crud_delete_user(db, user_id)
    except LastSuperAdminError as exc:
        raise _last_super_admin_conflict(exc) from exc

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put("/users/{user_id}/activate")
async def activate_user(
    user_id: int,
    current_user: User = Depends(require_role(ADMIN_ROLE)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Activate a user (admin and above, super admin for admin accounts)."""
    target = await _load_target(db, user_id)
    _assert_may_manage(current_user, target)

    user = await crud_activate_user(db, user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    return {"message": f"User {user.username} activated successfully"}


@router.put("/users/{user_id}/deactivate")
async def deactivate_user(
    user_id: int,
    current_user: User = Depends(require_role(ADMIN_ROLE)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Deactivate a user (admin and above, super admin for admin accounts).

    Deactivating your own account is refused so that an operator cannot lock
    themselves out; this is checked independently of the last-super-admin
    guard, which only covers the final super admin.
    """
    if current_user.id == user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot deactivate your own account",
        )

    target = await _load_target(db, user_id)
    _assert_may_manage(current_user, target)

    try:
        user = await crud_deactivate_user(db, user_id)
    except LastSuperAdminError as exc:
        raise _last_super_admin_conflict(exc) from exc

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    return {"message": f"User {user.username} deactivated successfully"}
