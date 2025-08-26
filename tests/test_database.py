# --------------------------------------------------------------------------
# Tests for database configuration and operations
#
# @author bnbong bbbong9@gmail.com
# --------------------------------------------------------------------------
import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import SQLModel

from src.models.users import APIKey, User
from tests.conftest import test_engine


class TestDatabase:
    """Test cases for database operations."""

    @pytest_asyncio.fixture
    async def test_db_session(self, db_session: AsyncSession) -> AsyncSession:
        """Create a test database session with tables."""
        # Tables are already created in conftest.py
        return db_session

    async def test_init_db(self, test_db_session: AsyncSession) -> None:
        """Test database initialization."""
        # Test that tables can be created
        # Note: init_db() uses the main engine, not test engine
        # So we'll test table creation directly with test engine

        async with test_engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)

        # Verify that tables exist by trying to query them
        result = await test_db_session.execute(
            text("SELECT name FROM sqlite_master WHERE type='table'")
        )
        tables = [row[0] for row in result.fetchall()]

        assert "users" in tables
        assert "api_keys" in tables

    async def test_user_model_creation(self, test_db_session: AsyncSession) -> None:
        """Test User model creation and retrieval."""
        # Create a test user
        user = User(
            username="testuser",
            email="test@example.com",
            hashed_password="hashed_password_123",
            full_name="Test User",
            is_active=True,
            is_superuser=False,
        )

        test_db_session.add(user)
        await test_db_session.commit()
        await test_db_session.refresh(user)

        # Verify user was created
        assert user.id is not None
        assert user.username == "testuser"
        assert user.email == "test@example.com"
        assert user.hashed_password == "hashed_password_123"
        assert user.full_name == "Test User"
        assert user.is_active is True
        assert user.is_superuser is False
        assert user.created_at is not None

    async def test_api_key_model_creation(self, test_db_session: AsyncSession) -> None:
        """Test APIKey model creation and retrieval."""
        # Create a test user first
        user = User(
            username="apiuser",
            email="api@example.com",
            hashed_password="hashed_password_456",
            is_active=True,
        )
        test_db_session.add(user)
        await test_db_session.commit()
        await test_db_session.refresh(user)

        # Create an API key
        api_key = APIKey(
            key_name="test-api-key",
            key_hash="hashed_api_key_123",
            user_id=user.id,
            is_active=True,
        )

        test_db_session.add(api_key)
        await test_db_session.commit()
        await test_db_session.refresh(api_key)

        # Verify API key was created
        assert api_key.id is not None
        assert api_key.key_name == "test-api-key"
        assert api_key.key_hash == "hashed_api_key_123"
        assert api_key.user_id == user.id
        assert api_key.is_active is True
        assert api_key.created_at is not None

    async def test_user_model_repr(self, test_db_session: AsyncSession) -> None:
        """Test User model string representation."""
        user = User(
            username="repruser",
            email="repr@example.com",
            hashed_password="hashed_password_789",
        )

        test_db_session.add(user)
        await test_db_session.commit()
        await test_db_session.refresh(user)

        # Test string representation
        repr_str = repr(user)
        assert "User" in repr_str
        assert "repruser" in repr_str
        assert "repr@example.com" in repr_str
        assert str(user.id) in repr_str

    async def test_api_key_model_repr(self, test_db_session: AsyncSession) -> None:
        """Test APIKey model string representation."""
        # Create a test user first
        user = User(
            username="apirepruser",
            email="apirepr@example.com",
            hashed_password="hashed_password_999",
        )
        test_db_session.add(user)
        await test_db_session.commit()
        await test_db_session.refresh(user)

        # Create an API key
        api_key = APIKey(
            key_name="repr-api-key",
            key_hash="hashed_api_key_999",
            user_id=user.id,
        )

        test_db_session.add(api_key)
        await test_db_session.commit()
        await test_db_session.refresh(api_key)

        # Test string representation
        repr_str = repr(api_key)
        assert "APIKey" in repr_str
        assert "repr-api-key" in repr_str
        assert str(api_key.id) in repr_str
        assert str(user.id) in repr_str

    async def test_user_unique_constraints(self, test_db_session: AsyncSession) -> None:
        """Test User model unique constraints."""
        # Create first user
        user1 = User(
            username="uniqueuser",
            email="unique@example.com",
            hashed_password="hashed_password_111",
        )
        test_db_session.add(user1)
        await test_db_session.commit()

        # Try to create user with same username (should fail)
        user2 = User(
            username="uniqueuser",  # Same username
            email="different@example.com",
            hashed_password="hashed_password_222",
        )
        test_db_session.add(user2)

        with pytest.raises(Exception):  # Should raise unique constraint violation
            await test_db_session.commit()

        await test_db_session.rollback()

        # Try to create user with same email (should fail)
        user3 = User(
            username="differentuser",
            email="unique@example.com",  # Same email
            hashed_password="hashed_password_333",
        )
        test_db_session.add(user3)

        with pytest.raises(Exception):  # Should raise unique constraint violation
            await test_db_session.commit()

    async def test_user_default_values(self, test_db_session: AsyncSession) -> None:
        """Test User model default values."""
        user = User(
            username="defaultuser",
            email="default@example.com",
            hashed_password="hashed_password_default",
        )

        test_db_session.add(user)
        await test_db_session.commit()
        await test_db_session.refresh(user)

        # Check default values
        assert user.is_active is True
        assert user.is_superuser is False
        assert user.full_name is None
        assert user.created_at is not None
        assert user.updated_at is None  # Should be None until updated

    async def test_api_key_default_values(self, test_db_session: AsyncSession) -> None:
        """Test APIKey model default values."""
        # Create a test user first
        user = User(
            username="apidefaultuser",
            email="apidefault@example.com",
            hashed_password="hashed_password_default",
        )
        test_db_session.add(user)
        await test_db_session.commit()
        await test_db_session.refresh(user)

        # Create API key with minimal data
        api_key = APIKey(
            key_name="default-api-key",
            key_hash="hashed_api_key_default",
            user_id=user.id,
        )

        test_db_session.add(api_key)
        await test_db_session.commit()
        await test_db_session.refresh(api_key)

        # Check default values
        assert api_key.is_active is True
        assert api_key.created_at is not None
        assert api_key.last_used_at is None  # Should be None until used
