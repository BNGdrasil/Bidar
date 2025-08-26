# --------------------------------------------------------------------------
# Database configuration for the Auth Server
#
# @author bnbong bbbong9@gmail.com
# --------------------------------------------------------------------------
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel

from .config import settings

# Create async engine
engine = create_async_engine(
    settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://"),
    echo=settings.DEBUG,
    pool_pre_ping=True,
    pool_recycle=300,
)

# Create session factory
AsyncSessionLocal = sessionmaker(
    bind=engine, class_=AsyncSession, expire_on_commit=False
)  # type: ignore


async def init_db() -> None:
    """Initialize database tables."""
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Get database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
