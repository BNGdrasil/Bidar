# --------------------------------------------------------------------------
# users CRUD method module
#
# @author bnbong bbbong9@gmail.com
# --------------------------------------------------------------------------
from typing import List, Optional

from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select as sqlmodel_select

from src.core.roles import DEFAULT_ROLE, SUPER_ADMIN_ROLE, is_superuser_role
from src.crud.auth import get_password_hash
from src.models.users import User, UserCreate, UserUpdate


class LastSuperAdminError(RuntimeError):
    """Raised when an operation would remove the last active super admin."""


async def count_active_super_admins(
    db: AsyncSession, exclude_user_id: Optional[int] = None
) -> int:
    """Count active super admins, optionally excluding one user."""
    statement = (
        sqlmodel_select(func.count())
        .select_from(User)
        .where(User.role == SUPER_ADMIN_ROLE)
        .where(User.is_active == True)  # noqa: E712
    )
    if exclude_user_id is not None:
        statement = statement.where(User.id != exclude_user_id)
    result = await db.execute(statement)
    return int(result.scalar_one())


async def _guard_last_super_admin(db: AsyncSession, user: User) -> None:
    """Refuse changes that would leave the system without a super admin.

    Every active super admin row, including the one being changed, is locked
    with SELECT ... FOR UPDATE before counting. Locking only the other rows
    would still let two concurrent demotions of two different super admins
    each see the other as the survivor and commit, leaving none. The rows are
    locked in id order so that concurrent callers cannot deadlock, and the
    caller commits the write in the same transaction, which every caller in
    this module does.

    SQLite ignores row locking, so the test suite exercises the same code path
    without a dialect branch; the protection is real on PostgreSQL.
    """
    if str(user.role) != SUPER_ADMIN_ROLE or not user.is_active:
        return

    statement = (
        sqlmodel_select(User)
        .where(User.role == SUPER_ADMIN_ROLE)
        .where(User.is_active == True)  # noqa: E712
        .order_by(User.id)  # type: ignore[arg-type]
        .with_for_update()
    )
    result = await db.execute(statement)
    locked = result.scalars().all()

    remaining = [row for row in locked if row.id != user.id]
    if not remaining:
        raise LastSuperAdminError(
            "Cannot remove, demote or deactivate the last active super admin."
        )


async def create_user(db: AsyncSession, user_create: UserCreate) -> User:
    """Create a new user.

    ``is_superuser`` is never taken from the input; it is derived from the
    role so that both columns cannot drift apart.
    """
    user_data = user_create.model_dump(exclude={"password", "is_superuser"})
    role = str(user_data.get("role") or DEFAULT_ROLE)
    user_data["role"] = role
    user_data["is_superuser"] = is_superuser_role(role)
    user_data["hashed_password"] = get_password_hash(user_create.password)

    user = User(**user_data)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def get_user_by_id(db: AsyncSession, user_id: int) -> Optional[User]:
    """Get user by ID."""
    result = await db.execute(sqlmodel_select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def get_user_by_username(db: AsyncSession, username: str) -> Optional[User]:
    """Get user by username."""
    result = await db.execute(sqlmodel_select(User).where(User.username == username))
    return result.scalar_one_or_none()


async def get_user_by_email(db: AsyncSession, email: str) -> Optional[User]:
    """Get user by email."""
    result = await db.execute(sqlmodel_select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def get_users(db: AsyncSession, skip: int = 0, limit: int = 100) -> List[User]:
    """Get list of users."""
    result = await db.execute(sqlmodel_select(User).offset(skip).limit(limit))
    return list(result.scalars().all())


async def update_user(
    db: AsyncSession, user_id: int, user_update: UserUpdate
) -> Optional[User]:
    """Update user.

    Raises:
        LastSuperAdminError: If the change would demote or deactivate the last
            active super admin.
    """
    user = await get_user_by_id(db, user_id)
    if not user:
        return None

    update_data = user_update.model_dump(exclude_unset=True, exclude={"is_superuser"})

    demotes = "role" in update_data and update_data["role"] != SUPER_ADMIN_ROLE
    deactivates = update_data.get("is_active") is False
    if demotes or deactivates:
        await _guard_last_super_admin(db, user)

    for field, value in update_data.items():
        setattr(user, field, value)

    # Keep the legacy flag consistent with the role on every write.
    user.is_superuser = is_superuser_role(str(user.role))

    await db.commit()
    await db.refresh(user)
    return user


async def delete_user(db: AsyncSession, user_id: int) -> bool:
    """Delete user.

    Raises:
        LastSuperAdminError: If the user is the last active super admin.
    """
    user = await get_user_by_id(db, user_id)
    if not user:
        return False

    await _guard_last_super_admin(db, user)

    await db.delete(user)
    await db.commit()
    return True


async def activate_user(db: AsyncSession, user_id: int) -> Optional[User]:
    """Activate user."""
    return await update_user(db, user_id, UserUpdate(is_active=True))


async def deactivate_user(db: AsyncSession, user_id: int) -> Optional[User]:
    """Deactivate user."""
    return await update_user(db, user_id, UserUpdate(is_active=False))
