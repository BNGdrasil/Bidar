# --------------------------------------------------------------------------
# users CRUD method module
#
# @author bnbong bbbong9@gmail.com
# --------------------------------------------------------------------------
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select as sqlmodel_select

from src.crud.auth import get_password_hash
from src.models.users import User, UserCreate, UserUpdate


async def create_user(db: AsyncSession, user_create: UserCreate) -> User:
    """Create a new user."""
    user_data = user_create.model_dump(exclude={"password"})
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
    """Update user."""
    result = await db.execute(sqlmodel_select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        return None

    update_data = user_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(user, field, value)

    await db.commit()
    await db.refresh(user)
    return user


async def delete_user(db: AsyncSession, user_id: int) -> bool:
    """Delete user."""
    result = await db.execute(sqlmodel_select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        return False

    await db.delete(user)
    await db.commit()
    return True


async def activate_user(db: AsyncSession, user_id: int) -> Optional[User]:
    """Activate user."""
    return await update_user(db, user_id, UserUpdate(is_active=True))


async def deactivate_user(db: AsyncSession, user_id: int) -> Optional[User]:
    """Deactivate user."""
    return await update_user(db, user_id, UserUpdate(is_active=False))
