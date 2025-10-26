# --------------------------------------------------------------------------
# Tests for user management functionality
#
# @author bnbong bbbong9@gmail.com
# --------------------------------------------------------------------------
import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.crud.auth import get_password_hash
from src.crud.users import activate_user as crud_activate_user
from src.crud.users import create_user
from src.crud.users import deactivate_user as crud_deactivate_user
from src.crud.users import get_users
from src.models.users import User
from src.schemas.users import UserRegisterRequest


class TestUserManagement:
    """Test cases for user management functions."""

    @pytest_asyncio.fixture
    async def test_user(self, db_session: AsyncSession) -> User:
        """Create a test user."""
        user = User(
            username="testuser",
            email="test@example.com",
            hashed_password=get_password_hash("testpassword123"),
            full_name="Test User",
            is_active=True,
            is_superuser=False,
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)
        return user

    @pytest_asyncio.fixture
    async def test_superuser(self, db_session: AsyncSession) -> User:
        """Create a test superuser."""
        superuser = User(
            username="admin",
            email="admin@example.com",
            hashed_password=get_password_hash("adminpassword123"),
            full_name="Admin User",
            is_active=True,
            is_superuser=True,
        )
        db_session.add(superuser)
        await db_session.commit()
        await db_session.refresh(superuser)
        return superuser

    async def test_register_user_success(self, db_session: AsyncSession) -> None:
        """Test successful user registration."""
        user_data = {
            "username": "newuser",
            "email": "newuser@example.com",
            "password": "newpassword123",
            "full_name": "New User",
        }

        user_request = UserRegisterRequest(
            username=str(user_data["username"]),
            email=str(user_data["email"]),
            password=str(user_data["password"]),
            full_name=str(user_data["full_name"]),
        )
        result = await create_user(db_session, user_request)

        assert result.username == user_data["username"]
        assert result.email == user_data["email"]
        assert result.full_name == user_data["full_name"]
        assert result.is_active is True
        assert result.is_superuser is False
        assert result.id is not None

        # Verify user was actually created in database
        result_query = await db_session.execute(
            select(User).where(User.username == user_data["username"])  # type: ignore
        )
        user = result_query.scalar_one_or_none()
        assert user is not None
        assert user.username == user_data["username"]
        assert user.email == user_data["email"]
        assert user.full_name == user_data["full_name"]
        assert user.is_active is True
        assert user.is_superuser is False

    async def test_create_user_duplicate_username(
        self, db_session: AsyncSession, test_user: User
    ) -> None:
        """Test user creation with duplicate username."""
        user_request = UserRegisterRequest(
            username=test_user.username,  # Same username as existing user
            email="different@example.com",
            password="differentpassword123",
            full_name="Different User",
        )

        with pytest.raises(Exception):  # Should raise database constraint error
            await create_user(db_session, user_request)

    async def test_create_user_duplicate_email(
        self, db_session: AsyncSession, test_user: User
    ) -> None:
        """Test user creation with duplicate email."""
        user_request = UserRegisterRequest(
            username="differentuser",
            email=test_user.email,  # Same email as existing user
            password="differentpassword123",
            full_name="Different User",
        )

        with pytest.raises(Exception):  # Should raise database constraint error
            await create_user(db_session, user_request)

    async def test_create_user_without_full_name(
        self, db_session: AsyncSession
    ) -> None:
        """Test user creation without full name."""
        user_request = UserRegisterRequest(
            username="nofullname",
            email="nofullname@example.com",
            password="password123",
        )
        result = await create_user(db_session, user_request)

        assert result.username == "nofullname"
        assert result.email == "nofullname@example.com"
        assert result.full_name is None

        # Verify user was created with null full_name
        result_query = await db_session.execute(
            select(User).where(User.username == "nofullname")  # type: ignore
        )
        user = result_query.scalar_one_or_none()
        assert user is not None
        assert user.full_name is None

    async def test_list_users_superuser_access(
        self, db_session: AsyncSession, test_superuser: User
    ) -> None:
        """Test listing users with superuser access."""
        # Create additional users
        user1 = User(
            username="user1",
            email="user1@example.com",
            hashed_password=get_password_hash("password1"),
            is_active=True,
        )
        user2 = User(
            username="user2",
            email="user2@example.com",
            hashed_password=get_password_hash("password2"),
            is_active=False,
        )
        db_session.add_all([user1, user2])
        await db_session.commit()

        # Test listing users
        users = await get_users(db_session)

        # Should return all users including superuser
        assert len(users) >= 3  # At least test_superuser, user1, user2

        # Verify user data structure
        for user in users:
            assert hasattr(user, "id")
            assert hasattr(user, "username")
            assert hasattr(user, "email")
            assert hasattr(user, "full_name")
            assert hasattr(user, "is_active")
            assert hasattr(user, "is_superuser")
            assert hasattr(user, "created_at")

    async def test_get_users_with_pagination(self, db_session: AsyncSession) -> None:
        """Test getting users with pagination."""
        # Create additional users
        for i in range(5):
            user = User(
                username=f"user{i}",
                email=f"user{i}@example.com",
                hashed_password=get_password_hash(f"password{i}"),
            )
            db_session.add(user)
        await db_session.commit()

        # Test pagination
        users_page1 = await get_users(db_session, skip=0, limit=3)
        users_page2 = await get_users(db_session, skip=3, limit=3)

        assert len(users_page1) <= 3
        assert len(users_page2) <= 3

    async def test_activate_user(self, db_session: AsyncSession) -> None:
        """Test activating user."""
        # Create inactive user
        inactive_user = User(
            username="inactiveuser",
            email="inactive@example.com",
            hashed_password=get_password_hash("inactivepassword"),
            is_active=False,
        )
        db_session.add(inactive_user)
        await db_session.commit()
        await db_session.refresh(inactive_user)

        # Activate user
        result = await crud_activate_user(db_session, int(inactive_user.id))  # type: ignore

        assert result is not None
        assert result.is_active is True
        assert result.username == "inactiveuser"

        # Verify user is now active in database
        result_query = await db_session.execute(
            select(User).where(User.id == inactive_user.id)  # type: ignore
        )
        user = result_query.scalar_one_or_none()
        assert user is not None
        assert user.is_active is True

    async def test_activate_nonexistent_user(self, db_session: AsyncSession) -> None:
        """Test activating non-existent user."""
        result = await crud_activate_user(db_session, 99999)  # Non-existent user ID
        assert result is None

    async def test_deactivate_user(self, db_session: AsyncSession) -> None:
        """Test deactivating user."""
        # Create active user
        active_user = User(
            username="activeuser",
            email="active@example.com",
            hashed_password=get_password_hash("activepassword"),
            is_active=True,
        )
        db_session.add(active_user)
        await db_session.commit()
        await db_session.refresh(active_user)

        # Deactivate user
        result = await crud_deactivate_user(db_session, int(active_user.id))  # type: ignore

        assert result is not None
        assert result.is_active is False
        assert result.username == "activeuser"

        # Verify user is now inactive in database
        result_query = await db_session.execute(
            select(User).where(User.id == active_user.id)  # type: ignore
        )
        user = result_query.scalar_one_or_none()
        assert user is not None
        assert user.is_active is False

    async def test_deactivate_nonexistent_user(self, db_session: AsyncSession) -> None:
        """Test deactivating non-existent user."""
        result = await crud_deactivate_user(db_session, 99999)  # Non-existent user ID
        assert result is None

    async def test_create_user_password_hashing(self, db_session: AsyncSession) -> None:
        """Test that user creation properly hashes passwords."""
        user_request = UserRegisterRequest(
            username="passwordtestuser",
            email="passwordtest@example.com",
            password="plaintextpassword",
            full_name="Password Test User",
        )

        created_user = await create_user(db_session, user_request)

        # Verify password was hashed
        assert created_user.hashed_password != "plaintextpassword"
        assert created_user.hashed_password.startswith("$2b$")  # bcrypt hash format

    async def test_user_registration_timestamps(self, db_session: AsyncSession) -> None:
        """Test that user registration sets proper timestamps."""
        user_data = {
            "username": "timestampuser",
            "email": "timestamp@example.com",
            "password": "timestamppassword",
        }

        user_request = UserRegisterRequest(
            username=user_data["username"],
            email=user_data["email"],
            password=user_data["password"],
        )
        await create_user(db_session, user_request)

        # Verify timestamps
        result_query = await db_session.execute(
            select(User).where(User.username == user_data["username"])  # type: ignore
        )
        user = result_query.scalar_one_or_none()
        assert user is not None
        assert user.created_at is not None
        assert user.updated_at is None  # Should be None until updated
